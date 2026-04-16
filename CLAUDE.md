# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development

```
make serve   # serves files at http://localhost:8000 via Python HTTP server
```

## Architecture

This repo contains standalone single-file HTML simulations — no build step, no dependencies. Each `.html` file is self-contained with inline CSS and JS.

- `clusters_particle_sim_v1.html` — original layout (canvas above controls)
- `clusters_particle_sim_v2.html` — two-column responsive layout (canvas left, controls right at ≥720px); also fixes trail color artifacts via a two-canvas approach
- `index.html` — simple landing page linking to both versions

## Data

### Chile protest dataset

Input file: `/Users/patcon/Downloads/chile-protest-highly-variable-test.h5ad`

The `.X` layer contains NaN values — always use `--layer X_masked_imputed_mean` when running `derive_forces.py` on this file:

```
uv run derive_forces.py --input ~/Downloads/chile-protest-highly-variable-test.h5ad \
  --n-species 5 --layer X_masked_imputed_mean --min-cluster-size 2 --k-gain 50 \
  --output chile_protest_config.json
```

Start with `--n-species 5` — it produces more interesting asymmetric dynamics than 4. Use `--min-cluster-size 2` so HDBSCAN can find enough clusters; `--k-gain 50` keeps forces from saturating at ±1.

### Trail rendering (v2)

The trail effect uses two canvases: an offscreen `trailCanvas` where particles are drawn and faded via `destination-out` compositing, and the main canvas which always fills a solid `#080808` background before compositing the trail on top. This avoids integer-rounding artifacts where 8-bit pixel values get stuck slightly off the background color when using a semi-transparent `fillRect` fade on a single canvas.
