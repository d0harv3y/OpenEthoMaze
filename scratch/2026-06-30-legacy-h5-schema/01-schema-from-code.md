# Legacy VAST H5 schema (from code archaeology)

Documented from `maze/core/schema.py`, `maze/pipeline/process_trial.py`, `maze/pipeline/metrics/exit_metrics.py`, `docs/h5_tracking_contract.md`, and consumers in `compile.py` / `block_dwell_average.py`.

## Trial group path

```
/<animal_id>/<session_id>/<trial_id>/
```

Example: `3243/S01/T01`. Trial attrs include `fps`, `px_per_cm`, `arena_center_*_px`, `exit_x`/`exit_y`, `video_path`, `sleap_path`, `primary_trajectory` (defaults `spot_hybrid`).

## `ambulation_metrics/` (legacy anchor source — ADR-0002)

Group name may be `ambulation metrics` (space) on older files — use `resolve_ambulation_metrics_group`.

Per tracking point (priority for readers: `spot_hybrid` → `center` → `spot`):

```
ambulation_metrics/<point>/xy    # structured array, dtype XY_ROW_DTYPE
ambulation_metrics/<point>/summary   # optional banded NODE_SUMMARY_BY_STATE_DTYPE
ambulation_metrics/<point>/movement_bouts   # optional bout list
```

### `XY_ROW_DTYPE` columns (`maze/core/schema.py`)

| Field | Type | Role |
|-------|------|------|
| `frame_index` | uint32 | Index into **source video** timeline; if absent at write, `0..n-1` |
| `t_s` | float64 | Row time |
| `x`, `y` | float32 | Position px |
| `dist_to_exit_px` | float32 | |
| `trial_state` | S16 | `excluded` / `iti_wait` / `run` (bytes strings) |
| `region_code` | S16 | |
| `valid` | uint8 | |
| `is_moving` | uint8 | Pipeline-computed movement mask (run band; hysteresis from `ambulation.py`) |

**Written by** `process_trial` → `build_xy_table_with_exit` after `calculate_ambulation_metrics` on ITI and RUN bands separately. `is_moving` is expanded to full-video length; movement bouts only label RUN band rows in practice.

**Anchor speed (S1 intent):** derive m/s from consecutive `(x,y)` on `spot_hybrid` rows (not stored as a column). Use RUN-phase rows (`trial_state == 'run'`) for calibration pool; join to producers on `(trial_key, source_frame_index)` where `source_frame_index` is the `frame_index` column (or row index when column equals `0..n-1`).

## `tracking/` (v2 — present in `kpms_tracking.h5`)

```
tracking/anatomical/   frame_index (T,), xy (T,K,2), score, valid
tracking/blob/       frame_index, xy, heading_rad, score, valid
```

Aligned to acquisition video timeline (`frame_index` monotonic). **Does not** include `trial_state` or `is_moving`. kpMS preprocess reads anatomical from here when `db_path` points at this H5.

## Join semantics (S0 / frame_alignment)

- `BehaviorLabeling.source_frame_index` = original video frame indices (strictly increasing, gaps allowed).
- `kpms_aligned_coordinates_and_indices` returns `source_frame_indices` mapping each kpMS row → video frame.
- `trial_state_for_rows(raw_states, source_frame_indices)` in `bout_kinematics.py` indexes full-trial `trial_state` array by source frame.

**Critical:** kpMS apply drops frames (NaN filter, confidence fragment filter). Legacy `xy` is typically **dense** over video frames; join is **many legacy rows → subset of kpMS rows** via `source_frame_index`, not equal length.

## `vast_results_legacy.h5` vs `kpms_tracking.h5`

| File | Role in handoff | On this machine |
|------|-----------------|-----------------|
| `vast_results_legacy.h5` | Pipeline-analyzed DB with `ambulation_metrics/*/xy` | **Missing** (`sack/test/`, `E:\vast_analysis\test\`) |
| `kpms_tracking.h5` | Tracking v2 materialization for kpMS (`compile` used as `db_path`) | **Present** — 2183 trials, **0** trials with `ambulation_metrics/*/xy` |

`compile_bout_features` on test2 did **not** pass `--legacy-db`; bout `trial_state` columns may be empty in stage_ii CSV.
