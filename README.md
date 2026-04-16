# Particle Life from High Dimensions

[Particle life](https://particle-life.com/) simulations where the force matrix is derived from real high-dimensional data rather than set randomly. The idea: if two cell types are near-neighbors in high-dimensional space, they attract; if they're far apart, they repel. Asymmetric forces (A attracts B but B repels A) emerge naturally from the directed neighborhood structure of the data.

## Simulations

Open `index.html` or load any file directly in a browser — no build step, no server needed.

| File | Notes |
|------|-------|
| `clusters_particle_sim_v1.html` | Original layout |
| `clusters_particle_sim_v2.html` | Two-column layout; fixes trail color artifacts via dual-canvas |
| `clusters_particle_sim_v3.html` | Adds per-species particle counts and JSON config import |

```
make serve   # serves at http://localhost:8000 via Python HTTP server
```

## Deriving a force matrix from data

`derive_forces.py` takes an [AnnData](https://anndata.readthedocs.io/) `.h5ad` file, runs [PaCMAP](https://github.com/YingfanWang/PaCMAP) to extract neighbor pair structure, clusters cells with HDBSCAN, then maps the directed pair densities to a force matrix via a tanh kernel.

```
uv run derive_forces.py --input data.h5ad --n-species 5 --output config.json
```

Load the resulting `config.json` into v3 via the **load config** button. Particle counts are set directly from cluster sizes.

### Key options

| Flag | Default | Effect |
|------|---------|--------|
| `--n-species` | required | Number of particle species (clusters) |
| `--layer` | `.X` | Use a specific layer or obsm key instead of `.X` |
| `--k-gain` | 200 | tanh gain — lower if forces saturate at ±1, raise if all near 0 |
| `--mn-weight` | 0.3 | Weight of mid-near pairs added to attraction signal |
| `--min-cluster-size` | 5 | HDBSCAN minimum cluster size — lower if not enough clusters found |

### Preserving asymmetry from the data

Asymmetric forces — A attracted to B while B flees A — are what produce chasing, orbiting, and swarming in particle life. The data can encode this naturally: cluster A may have many neighbors in cluster B without the reverse being true.

`derive_forces.py` preserves this by using PaCMAP's directed pair structure: pairs are stored as `(anchor, neighbor)` where the anchor is the point being embedded. Counting only `anchor=A → neighbor=B` (not both directions) gives `mat[A][B] ≠ mat[B][A]` whenever the neighborhood relationships are asymmetric in the data. An earlier version used undirected pair matching, which collapsed `mat[A][B]` and `mat[B][A]` to the same value and lost that signal.

## Example: Chile protest dataset

A social science dataset of protest event records encoded as high-dimensional vectors. The `.X` layer contains NaN values; use the imputed layer:

```
uv run derive_forces.py \
  --input ~/Downloads/chile-protest-highly-variable-test.h5ad \
  --n-species 5 \
  --layer X_masked_imputed_mean \
  --min-cluster-size 2 \
  --k-gain 50 \
  --output chile_protest_config.json
```

The committed `chile_protest_config.json` was produced with these settings. It yields 5 species with counts roughly proportional to cluster sizes in the data (~1500 dominant cluster, ~30–90 minority clusters), and a force range of roughly −0.6 to +1.0 with meaningful asymmetries between species.

Note: PaCMAP and HDBSCAN have stochastic components — re-runs will produce slightly different values.
