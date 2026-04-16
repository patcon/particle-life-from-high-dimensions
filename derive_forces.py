# /// script
# requires-python = "==3.10.*"
# dependencies = [
#   "h5py>=3.0",
#   # llvmlite 0.46+ dropped x86_64 wheels; pin for Intel Mac compatibility.
#   # See: https://github.com/numba/llvmlite/issues/1357
#   "llvmlite==0.45.1; platform_system == 'Darwin' and platform_machine == 'x86_64'",
#   "numba==0.62.1",
#   "pacmap==0.8.0",
#   "hdbscan>=0.8.38",
#   "scikit-learn>=1.3",
#   "numpy>=1.26",
# ]
# ///
"""
Derive a particle-life force matrix from high-dimensional biological data.

Builds NN/MN/FP pair lists using sklearn NearestNeighbors (no numba required),
then derives per-species-pair force scalars using the same kernel logic as PaCMAP.

Usage:
    uv run derive_forces.py --input data.h5ad --n-species 4 --output config.json
    uv run derive_forces.py --input data.h5ad --n-species 3 --layer X_masked_imputed_mean --output config.json

The output JSON can be loaded into clusters_particle_sim_v3.html via the "load config" button.
"""

import argparse
import json
import sys

import numpy as np
import h5py
import pacmap
from hdbscan.flat import HDBSCAN_flat


def parse_args():
    p = argparse.ArgumentParser(
        description="Derive particle-life force matrix from h5ad via KNN pairs + clustering"
    )
    p.add_argument("--input", required=True, help="Path to .h5ad file")
    p.add_argument(
        "--n-species",
        required=True,
        type=int,
        choices=[2, 3, 4, 5],
        metavar="{2-5}",
        help="Number of species (clusters) to derive",
    )
    p.add_argument("--output", required=True, help="Output JSON path")
    p.add_argument(
        "--layer",
        default=None,
        help="Layer or obsm key to use as input matrix (default: .X). "
             "Tries adata.layers[NAME] first, then adata.obsm[NAME].",
    )
    p.add_argument(
        "--min-cluster-size",
        type=int,
        default=5,
        help="Minimum cluster size for HDBSCAN (default: 5). Lower this if HDBSCAN "
             "can't find enough clusters.",
    )
    p.add_argument(
        "--k-gain",
        type=float,
        default=200.0,
        help="Gain for tanh force formula (default: 200). "
             "Lower if all forces saturate at ±1; raise if all near 0.",
    )
    p.add_argument(
        "--mn-weight",
        type=float,
        default=0.3,
        help="Weight of MN pairs added to attraction signal (default: 0.3)",
    )
    return p.parse_args()


def load_matrix(path, layer):
    """Read a matrix directly from the h5ad HDF5 file via h5py, bypassing uns metadata."""
    print(f"Loading {path}...", file=sys.stderr)

    with h5py.File(path, "r") as f:
        # Apply cluster_mask if present (filters out unmasked observations)
        if "obs/cluster_mask" in f:
            cluster_mask = f["obs/cluster_mask"][:]
            print(f"  Applying cluster_mask: {cluster_mask.sum()} / {len(cluster_mask)} cells kept", file=sys.stderr)
        else:
            cluster_mask = None

        if layer is None:
            # .X may be stored as a dense dataset or a sparse group
            if "X" in f:
                grp = f["X"]
                if isinstance(grp, h5py.Dataset):
                    X = grp[:]
                else:
                    # Sparse CSR/CSC stored as group with data/indices/indptr
                    data = grp["data"][:]
                    indices = grp["indices"][:]
                    indptr = grp["indptr"][:]
                    shape = tuple(grp.attrs.get("shape", f["obs"].attrs.get("_index", None)))
                    import scipy.sparse
                    X = scipy.sparse.csr_matrix((data, indices, indptr), shape=shape).toarray()
                source_desc = ".X"
            else:
                print("Error: no 'X' dataset found in h5ad file.", file=sys.stderr)
                sys.exit(1)
        elif f"layers/{layer}" in f:
            grp = f[f"layers/{layer}"]
            X = grp[:] if isinstance(grp, h5py.Dataset) else _read_sparse(grp)
            source_desc = f"layers['{layer}']"
        elif f"obsm/{layer}" in f:
            X = f[f"obsm/{layer}"][:]
            source_desc = f"obsm['{layer}']"
        else:
            available = list(f.get("layers", {}).keys()) + list(f.get("obsm", {}).keys())
            print(
                f"Error: layer '{layer}' not found. Available: {available}",
                file=sys.stderr,
            )
            sys.exit(1)

    X = np.array(X, dtype=np.float32)
    if cluster_mask is not None:
        X = X[cluster_mask]
    print(
        f"  {X.shape[0]} cells x {X.shape[1]} features from {source_desc}",
        file=sys.stderr,
    )
    if X.shape[0] > 50_000:
        print(f"  Warning: {X.shape[0]} cells is large; this may be slow.", file=sys.stderr)

    return X, path


def _read_sparse(grp):
    import scipy.sparse
    data = grp["data"][:]
    indices = grp["indices"][:]
    indptr = grp["indptr"][:]
    shape = tuple(grp.attrs["shape"])
    return scipy.sparse.csr_matrix((data, indices, indptr), shape=shape).toarray()


def run_pacmap(X):
    print("Fitting PaCMAP...", file=sys.stderr)
    assert hasattr(pacmap, "PaCMAP"), "pacmap module not found"
    pm = pacmap.PaCMAP(
        n_components=2,
        n_neighbors=None,  # let PaCMAP compute from data size (matches valency-anndata)
    )
    pm.fit_transform(X)

    assert hasattr(pm, "pair_neighbors"), (
        "pacmap.PaCMAP has no 'pair_neighbors' attribute — "
        "update to pacmap >= 0.7 (older versions use 'pairs_' prefix)"
    )
    nn_pairs = np.array(pm.pair_neighbors, dtype=np.int32)
    mn_pairs = np.array(pm.pair_MN, dtype=np.int32)
    fp_pairs = np.array(pm.pair_FP, dtype=np.int32)

    print(
        f"  NN pairs: {len(nn_pairs)}, MN pairs: {len(mn_pairs)}, FP pairs: {len(fp_pairs)}",
        file=sys.stderr,
    )
    return nn_pairs, mn_pairs, fp_pairs


def cluster_cells(X, n_species, min_cluster_size):
    print(
        f"Clustering into {n_species} species with HDBSCAN_flat "
        f"(min_cluster_size={min_cluster_size})...",
        file=sys.stderr,
    )
    result = HDBSCAN_flat(
        X,
        n_clusters=n_species,
        min_cluster_size=min_cluster_size,
        cluster_selection_method="leaf",
    )
    # API varies by version: some return (labels, probs), others return an object
    if hasattr(result, "labels_"):
        labels = np.array(result.labels_, dtype=np.int32)
    else:
        labels = np.array(result[0], dtype=np.int32)

    n_noise = int(np.sum(labels == -1))
    if n_noise > 0:
        print(
            f"  {n_noise} noise points — assigning to nearest cluster centroid.",
            file=sys.stderr,
        )
        cluster_ids = [s for s in range(n_species) if np.any(labels == s)]
        centroids = np.array([X[labels == s].mean(axis=0) for s in cluster_ids])
        noise_idx = np.where(labels == -1)[0]
        dists = np.linalg.norm(X[noise_idx, None, :] - centroids[None, :, :], axis=2)
        labels[noise_idx] = np.array(cluster_ids)[np.argmin(dists, axis=1)]

    counts = [int(np.sum(labels == s)) for s in range(n_species)]
    print(f"  Cluster sizes: {counts}", file=sys.stderr)
    return labels, counts


def pair_density_directed(pairs, labels, a, b, size_a, size_b):
    """Directed pair density: count a→b pairs normalized by size_a * size_b.

    PaCMAP stores pairs as (anchor, neighbor) where the anchor is the point
    being embedded. By counting only anchor=a, neighbor=b (not both directions),
    mat[A][B] ≠ mat[B][A] — giving the asymmetric forces that produce chasing
    and orbiting in particle life.

    Normalizing by size_a * size_b (same as the old symmetric formula) keeps
    values in the same scale regardless of cluster size, so k_gain defaults
    remain useful.
    """
    if len(pairs) == 0 or size_a == 0 or size_b == 0:
        return 0.0
    li = labels[pairs[:, 0]]  # anchor cluster
    lj = labels[pairs[:, 1]]  # neighbor cluster
    return float(np.sum((li == a) & (lj == b))) / (size_a * size_b)


def compute_force_matrix(labels, counts, nn_pairs, mn_pairs, fp_pairs, n_species, k_gain, mn_weight):
    mat = []
    for a in range(n_species):
        row = []
        for b in range(n_species):
            sa, sb = counts[a], counts[b]
            nn_d = pair_density_directed(nn_pairs, labels, a, b, sa, sb)
            mn_d = pair_density_directed(mn_pairs, labels, a, b, sa, sb)
            fp_d = pair_density_directed(fp_pairs, labels, a, b, sa, sb)
            attraction = nn_d + mn_weight * mn_d
            force = float(np.tanh(k_gain * (attraction - fp_d)))
            row.append(round(force, 4))
        mat.append(row)
    return mat


def main():
    args = parse_args()
    X, source_path = load_matrix(args.input, args.layer)
    nn_pairs, mn_pairs, fp_pairs = run_pacmap(X)
    labels, counts = cluster_cells(X, args.n_species, args.min_cluster_size)
    mat = compute_force_matrix(
        labels, counts, nn_pairs, mn_pairs, fp_pairs,
        args.n_species, args.k_gain, args.mn_weight,
    )

    output = {
        "nS": args.n_species,
        "mat": mat,
        "counts": counts,
        "source": source_path,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Wrote {args.output}", file=sys.stderr)

    flat = [v for row in mat for v in row]
    print(
        f"Force matrix range: min={min(flat):.3f}, max={max(flat):.3f}, "
        f"mean={sum(flat)/len(flat):.3f}",
        file=sys.stderr,
    )
    if max(abs(v) for v in flat) < 0.1:
        print(
            "  Hint: forces are all near zero — try lowering --k-gain (e.g. --k-gain 50)",
            file=sys.stderr,
        )
    elif min(abs(v) for v in flat if abs(v) > 0.01) > 0.9:
        print(
            "  Hint: forces are saturating at ±1 — try lowering --k-gain (e.g. --k-gain 10)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
