# kpMS post-processing: review, merge, bout cleanup

ORM wraps **keypoint-moseq** for three stages after fit/apply. Order matters: **review** (no file changes) → **semantic merge** (collapse syllable IDs) → **bout cleanup** (temporal rules on the label stream).

## 1. Review artifacts (taxonomy)

Script: `scripts/kpms_review_artifacts.py`

Generates, under `<model-dir>/review/` (or `--output-dir`):

- **Grid movies** — `kpms.generate_grid_movies` (many instances per syllable).
- **Trajectory plots** — `kpms.generate_trajectory_plots` (pose loops; optional GIFs).
- **Similarity matrix** — CSV from `kpms.syllable_similarity` (pairwise distances between typical trajectories).

Inputs: `--results-h5`, `--manifest-csv` (default `<model-dir>/selected_trials.csv`), and `--model-dir`. Coordinates come from `maze.kpms.preprocess.build_kpms_inputs` (same as fit/apply). Use `--retain-all-sleap-frames` when results align to full-length native kpMS runs. If videos are missing, use `--keypoints-only` for pose-only grid movies.

Requires: `uv sync --extra kpms`

## 2. Semantic merge (user-defined groups)

Script: `scripts/kpms_apply_syllable_merge.py`

Merge spec (YAML or JSON):

```yaml
groups:
  - [1, 3, 5]
  - [2, 4]
```

This calls `kpms.generate_syllable_mapping` and `kpms.apply_syllable_mapping`, then writes a new HDF5 plus `*.merge_meta.json` and HDF5 attrs. The merge is **only** what you list; inspect grid/trajectory plots first, optionally using the similarity CSV to suggest clusters.

## 3. Bout cleanup (pluggable steps)

Module: `maze.kpms.syllable_bout_clean`

Script: `scripts/kpms_clean_syllable_bouts.py`

**Presets** (CLI `--preset`):

- `conservative` / `drop_only` — `drop_short_runs` only, using the same minimum duration scale as movement bouts (`MIN_MOVEMENT_BOUT_DURATION_S` in `maze.pipeline.defaults`).
- `movement_like` — `drop_short_runs` + `bridge_same_label` with gap width from `MOVEMENT_INTER_BOUT_INTERVAL_S`. Bridging uses `gap_policy: noise_only`; with an **empty** `noise_labels` set, **no bridging occurs** (gap must be filled only with labels you allow as “noise”). To bridge across short junk syllables, use a **YAML config** and list those ids under `noise_labels`.

**Custom config** (YAML/JSON):

```yaml
fps: 30
preset: conservative
```

Or explicit steps:

```yaml
fps: 30
steps:
  - type: drop_short_runs
    min_bout_s: 0.166
    orphan_policy: previous
  - type: bridge_same_label
    max_gap_s: 0.166
    gap_policy: noise_only
    noise_labels: [0, 15]
```

**Gap policies**

- `noise_only` — every frame in the intervening run must be in `noise_labels` (and not the bridged label `k`). Empty `noise_labels` disables bridging.
- `max_distinct` — bridge if the number of **distinct** labels in the gap (excluding `k`) is ≤ `max_distinct`.

**Limitation:** `bridge_same_label` considers **one** intervening run between two runs of the same label per iteration; the pipeline repeats until stable so chained gaps can be filled over multiple passes.

Output: new HDF5 plus `*.bout_clean_meta.json` and attrs.

## 4. Overlay / metrics

Point `render_trial_overlay` / analysis at the final `results_*.h5` you intend to use (merged and/or bout-cleaned), not the raw apply output, unless you explicitly want pre-post labels.
