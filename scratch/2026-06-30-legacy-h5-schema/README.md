# Legacy H5 schema investigation (S1 blocker)

## Task

Verify the on-disk schema for the **legacy VAST H5** used as the independent `is_moving` anchor source (ADR-0002): per-frame `spot_hybrid` XY, `trial_state`, `frame_index` semantics, and alignment with kpMS `source_frame_index` via `maze.kpms.frame_alignment`.

This is handoff S1 task 3 (`docs/handoffs/2026-06-29-behavior-ethogram-producers.md`).

## Background

- **Canonical dtype:** `XY_ROW_DTYPE` in `maze/core/schema.py`
- **Readers:** `compile._load_trial_states_legacy`, `block_dwell_average.load_trial_run_sample`, `read_xy_table` / `unified_overlay`
- **Expected anchor file:** `C:\Users\admin\Documents\work\sack\test\vast_results_legacy.h5` (handoff)
- **Available locally:** `C:\Users\admin\Documents\work\sack\test2\kpms_tracking.h5` (tracking v2 only)
- **Cohort manifest:** `test2\trial_manifest_kpms_tracking.csv` (2183+ rows)

## Checklist

- [x] Document expected schema from code → `01-schema-from-code.md`
- [x] Probe `kpms_tracking.h5` structure
- [x] Count trials with `ambulation_metrics/*/xy`
- [x] Run kpMS `frame_alignment` + speed comparison on sample trial `3243/S01/T01`
- [x] Probe `vast_results_legacy.h5` — `C:\Users\admin\Documents\work\sack\vast_results_legacy.h5` (161 animals)
- [x] Confirm `spot_hybrid` `frame_index` on real legacy file → dense `0..n-1`, equals row index
- [x] Verify `trial_state` bands on sample `3243/S01/T01` → `iti_wait` 278 + `run` 3331 (no `excluded` rows)
- [x] kpMS join via `source_frame_index` → 3497/3497 rows matched
- [ ] Compare stored `is_moving` column vs recomputed anchor from XY speed

## Findings

### 1. `vast_results_legacy.h5` location

- **Present:** `C:\Users\admin\Documents\work\sack\vast_results_legacy.h5` (161 root animals; full pipeline analysis)
- **Absent:** `sack\test\vast_results_legacy.h5` (handoff path was wrong subfolder)

Probe output: `legacy_alignment.json` (trial `3243/S01/T01`).

### 2. `kpms_tracking.h5` ≠ legacy anchor DB

Probe output: `scratch/2026-06-30-legacy-h5-schema/kpms_tracking_probe.json`

| Observation | Value |
|-------------|-------|
| Trials | 2183 |
| Trials with `ambulation_metrics` group | 2183 |
| Trials with any `ambulation_metrics/*/xy` | **0** |
| Per-trial `tracking/anatomical` | Present (`frame_index`, `xy`, `score`, `valid`) |

Every sampled trial has an **empty** `ambulation_metrics` group (placeholder for v2 layout). No `trial_state`, no `spot_hybrid`, no stored `is_moving`.

`compile_bout_features_summary.json` confirms stage_ii compile used `kpms_tracking.h5` as tracking DB with **no** `--legacy-db`.

### 3. Frame alignment (kpMS ↔ tracking H5) works; lengths differ

Trial `3243/S01/T01`, seed `042`, `db_path=kpms_tracking.h5`:

| Quantity | Value |
|----------|-------|
| `tracking/anatomical` rows | 3609 (`frame_index` 0..3608, strictly increasing) |
| kpMS aligned rows (`source_frame_index`) | 3497 |
| `src_idx` range | 0 .. 3608 (subset of video frames) |
| All `src_idx` ∈ tracking `frame_index` | Yes |

kpMS preprocessing **drops** ~112 frames; producer/anchor joins must use `source_frame_index`, not assume equal-length arrays.

### 4. Speed source independence (why ADR-0002 matters)

Centroid speed from `tracking/anatomical` at `src_idx` vs speed recomputed on kpMS-aligned coordinates (same trial):

- Pearson r ≈ **0.84**
- MAE ≈ **0.064 m/s**

Same db_path, different filtering/centroid path → **not tautological** if we used kpMS-row speed for anchor. `spot_hybrid` (controller hybrid trace) is a third source again — must probe on real `vast_results_legacy.h5`.

### 5. Verified on `3243/S01/T01` (`legacy_alignment.json`)

| Check | Result |
|-------|--------|
| Points with `xy` | `spot_hybrid`, `spot`, `centroid`, `in-range` — all `XY_ROW_DTYPE` |
| `primary_trajectory` attr | `spot_hybrid` ✓ |
| Rows / `frame_index` | 3609 rows; `frame_index` = `0..3608` dense, equals row index |
| `trial_state` | `iti_wait` 278, `run` 3331 — matches `trial_start_frame` attr 278; **no `excluded` band** on this trial |
| Stored `is_moving` (spot_hybrid) | 23.9% of frames moving |
| fps / px_per_cm | 27.75 / 2.406 (from trial attrs, not manifest) |
| Legacy speed (spot_hybrid XY) | p50 0.071 m/s, p95 0.48, max 1.62 |
| kpMS aligned rows | 3497 (`src_idx` 0..3608, strictly increasing) |
| Join `speed[src_idx]` | 3497 matched; p50 at kpMS rows 0.076 m/s |

**Adapter implication:** `source_frame_index` for anchor = legacy `frame_index` column (here identical to row index). Index legacy speed as `speed_mps[source_frame_index]` when joining to `BehaviorLabeling` / kpMS rows.

**Still open:** stored `is_moving` vs recomputed hysteresis anchor; whether other trials have `excluded` pre-iti rows.

## Scripts

```powershell
# Structure probe
uv run python scratch/2026-06-30-legacy-h5-schema/probe_legacy_h5.py `
  --h5 "PATH\to\vast_results_legacy.h5" `
  --max-trials 5 `
  --out scratch/2026-06-30-legacy-h5-schema/legacy_probe.json

# Alignment + join (once legacy H5 exists)
uv run python scratch/2026-06-30-legacy-h5-schema/probe_legacy_h5.py `
  --h5 "PATH\to\vast_results_legacy.h5" `
  --manifest "C:\Users\admin\Documents\work\sack\test2\trial_manifest_kpms_tracking.csv" `
  --trial "3243/S01/T01" `
  --kpms-root "C:\Users\admin\Documents\work\sack\test2" `
  --seed 042 `
  --out scratch/2026-06-30-legacy-h5-schema/alignment_probe.json
```

## Conclusions

1. **Schema matches code** — `spot_hybrid/xy` is the anchor trajectory; dtype exact match.
2. **Frame alignment is clean** on the probed trial — kpMS `source_frame_index` ⊂ legacy `frame_index`; join is direct integer indexing.
3. **`kpms_tracking.h5` remains unsuitable** for anchor (no ambulation xy); use `sack\vast_results_legacy.h5`.
4. **Handoff path correction:** legacy DB is `sack\vast_results_legacy.h5`, not `sack\test\...`.

## Recommended next steps

1. Implement `load_legacy_vast_speed` → `(source_frame_index, speed_mps, valid, trial_state)` from `spot_hybrid/xy` + trial attrs fps/px_per_cm.
2. TDD `is_moving(speed_mps, ...)` + optional check: recomputed vs stored `is_moving` column (sanity, not canonical).
3. Wire harness join on `(trial_key, source_frame_index)`.
