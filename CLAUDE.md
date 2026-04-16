# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development

```
make serve       # builds and serves with Eleventy dev server (pnpm)
make build       # builds static site into _site/
make prepare-gh  # create GitHub repo, push, and enable Pages via Actions
```

## Architecture

This repo uses **Eleventy** (Nunjucks templates) to build standalone HTML simulations. Source lives in `src/`, output goes to `_site/`. GitHub Actions builds and deploys `_site/` to Pages.

### Source structure

- `src/index.njk` — landing page
- `src/clusters_particle_sim_v1.njk` — original layout (canvas above controls); extends `base.njk`
- `src/clusters_particle_sim_v2.njk` — two-column responsive layout; extends `sim.njk`
- `src/clusters_particle_sim_v3.njk` — v2 + per-species counts + JSON config import; extends `sim.njk`

### Shared includes (`src/_includes/`)

- `base.njk` — HTML skeleton (DOCTYPE, head, body blocks)
- `sim.njk` — two-column sim layout; extends `base.njk`; defines `extraStyle`, `extraControls`, `script` blocks
- `sim-css.njk` — shared CSS for all sim pages
- `sim-js-core.njk` — shared JS: constants, `step()`, `updateOscillation()`, control handlers
- `sim-js-render-matrix.njk` — shared `renderMatrix()` (v1/v2; v3 defines its own with count row)
- `sim-js-two-canvas.njk` — offscreen canvas setup + `draw()` used by v2 and v3

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

### Label + slider pairing

Every label must be co-located with its control in a `<span class="ctrl-pair">` (or `<div class="ctrl-pair">`) so they never line-break separately. The `.ctrl-pair` class is `display: inline-flex; align-items: center; gap: 5px` (defined in `sim-css.njk`). This applies to all controls — in `sim.njk` static HTML and in any dynamically generated control HTML (e.g. `renderMatrix()` speaker section). Never place a bare `<label>` and its `<input>` as sibling flex children without this wrapper.

### Save config format (canonical)

v3 and v4 export a JSON file via the "save config" button. This is the canonical format — the load button and `derive_forces.py` will eventually migrate to it. **Any new force UI must be included in the save output.**

**V3 format:**
```json
{
  "nS": 4,
  "mat": [[...], ...],
  "counts": [60, 60, 60, 60],
  "locks": [[false, true, ...], ...],
  "physics": {
    "force": 1.8,
    "damping": 0.88,
    "rmax": 80,
    "rmin": 13,
    "trail": 8,
    "oscSpeed": 5
  }
}
```

**V4 adds a `speaker` key:**
```json
{
  "speaker": {
    "rmax": 200,
    "rmin": 20,
    "g": 0.5,
    "reactions": [...],
    "locks": [false, true, ...]
  }
}
```

### Trail rendering (v2/v3)

The trail effect uses two canvases: an offscreen `trailCanvas` where particles are drawn and faded via `destination-out` compositing, and the main canvas which always fills a solid `#080808` background before compositing the trail on top. This avoids integer-rounding artifacts where 8-bit pixel values get stuck slightly off the background color when using a semi-transparent `fillRect` fade on a single canvas.
