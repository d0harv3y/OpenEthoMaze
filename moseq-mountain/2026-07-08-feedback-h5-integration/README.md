# Legacy feedback ↔ pipeline H5 integration

## Task

Trace how `feedback/table` enters `vast_results_legacy.h5` from the legacy source DB, explain empty tail stimulus values and frame-index behavior, and identify errors / better integration paths.

## Background

- Prior finding: ~10.6% of bouts have blank `bout_mean_duty` / `bout_mean_dist_px` at trial tails ([`../2026-07-08-stimulus-end-bout-gaps/README.md`](../2026-07-08-stimulus-end-bout-gaps/README.md)).
- User hypothesis: feedback should align **only with `run` `trial_state`**; xy carries full timeline; avoiding redundant feedback in ambulation tables created tech debt.
- Cohort H5: `C:\Users\admin\Documents\work\sack\vast_results_legacy.h5`

## Checklist

- [x] Trace legacy import path (`maze-legacy-db init/sync`)
- [x] Trace pipeline xy write (`process_trial`)
- [x] Compare frame_index / trial_state semantics on sample trial
- [x] Verify stimulus join indexing assumption
- [x] Document errors and integration options

## Findings

### Two writers, two timelines

| Artifact | When written | Row count | `frame_index` | `trial_state` |
|----------|--------------|-----------|---------------|---------------|
| `feedback/table` | `legacy_db init/sync` via `write_feedback_series` | **run-only** (`n_source - trial_start_frame`) | `0 … n_run-1` (run-relative) | all `run` |
| `ambulation_metrics/*/xy` | `maze-legacy-db run` → `process_trial` | **full video** (`video_n_frames`) | `0 … n_video-1` (absolute) | `excluded` / `iti_wait` / `run` |

Sample trial `3245/S01/T01`:

| Field | Value |
|-------|-------|
| `trial_start_frame` (attr) | **278** |
| xy rows | 3600 (`iti_wait`: 278, `run`: 3322) |
| feedback rows | **3323** (all `run`) |
| `h5_n_frames` (source) | 3601 |
| gap `len(xy) - len(fb)` | **277** (= `trial_start_frame`, not coincidence) |

Feedback length = source H5 frames − ITI offset (`w[start:]`, `m[start:]`). Xy length = video frames. Off-by-one: source 3601 vs video 3600.

### Legacy import (`maze/cli/legacy_db.py` init + sync)

```python
start = trial_start_frame  # subtrial==1 in source H5
w_analysis = h5_data.w[start:]
m_analysis = h5_data.m[start:]
write_feedback_series(LEGACY_DB, key, w_analysis, m_analysis)
# trial_start_frame NOT passed to write_feedback_series
```

`write_feedback_series` (`maze/pipeline/db/feedback.py`):

- Builds `n = len(m)` run-only table.
- `fb["frame_index"] = arange(n)` — **0-based run-relative**, not absolute video index.
- Without `trial_start_frame` arg, all rows `trial_state = run` (correct for content, wrong for coordinate system).

`trial_start_frame` **is** stored on trial attrs via `write_trial_settings` — but feedback writer ignores it for indexing.

### Pipeline run (`process_trial.py`)

- Loads SLEAP trace for **full** `n_frames`.
- Writes xy via `build_xy_table_with_exit(..., seek_row, run_row)` over **full video** with proper `iti_wait` / `run` bands.
- **Does not rewrite** `feedback/table` — only reads it for incongruence QC (`read_feedback_series`, trim to `n_analysis`).
- Comment at L736: trim feedback to `n_analysis` for off-by-one with video — acknowledges length skew.

### Indexing bug (affects duty everywhere, tail blanks are symptom)

Stimulus join (`mean_scalar_over_rows`) maps kpMS `source_frame_indices` (absolute video frame) directly into `motor_fb[src]`:

```python
in_range = (frame_idx >= 0) & (frame_idx < len(vals))
picked = vals[frame_idx[in_range]]
```

Correct mapping for run-only feedback:

```text
motor_fb[absolute_frame - trial_start_frame]   when absolute_frame >= trial_start_frame
```

`compare_indexing.py` on `3245/S01/T01`:

| abs frame | direct `m[abs]` (current) | offset `m[abs-278]` (correct) |
|-----------|---------------------------|-------------------------------|
| 278 | 57.0 | **43.0** |
| 500 | 65.0 | **47.0** |
| 3323 | NaN (tail blank) | **79.0** |
| 3599 | NaN (tail blank) | **78.0** |

**Direct indexing is wrong for the whole run**, not only the tail. Tail empties appear when `abs_frame >= len(feedback)` (3323). Distance from xy uses absolute index and is mostly correct; `read_trial_stimulus_frames` truncates dist to `min(motor, dist)` so dist loses tail too.

### Design intent vs what shipped

**Intent (reasonable):**

- xy: full timeline + `trial_state` bands for ITI/run/excluded.
- feedback: run-phase motor only (no duplicate ITI duty in feedback table).

**Tech debt:**

1. Run-only feedback uses **run-relative** row indices without recording the offset in `frame_index` or attrs on `feedback/`.
2. Pipeline never **re-materializes** feedback onto the absolute video index after xy is written.
3. Consumers (stimulus join, overlay, incongruence QC) assume **shared absolute indexing** between xy and feedback.
4. `write_feedback_series(..., trial_start_frame=)` exists for iti/run labeling on a **full-length** table but legacy import doesn't use it.

### Errors identified

| # | Error | Severity |
|---|--------|----------|
| E1 | Feedback `frame_index` is run-relative; xy/kpMS use absolute — join uses wrong index for `motor_fb` | **High** — duty wrong cohort-wide |
| E2 | Feedback length from source H5 ≠ video length (3601−278 vs 3600) | Medium — 1-frame skew + tail |
| E3 | Legacy import omits `trial_start_frame` on `write_feedback_series` (all rows `run`) | Low for run-only content; blocks ITI duty audit |
| E4 | `process_trial` never aligns feedback to xy timeline | Medium — drift persists after pipeline |
| E5 | Stimulus reader `min(len(motor), len(dist))` clips dist when duty shorter | Medium — unnecessary tail loss |

## Better integration options

### A. Fix at read time (smallest, unblocks MI)

In `read_trial_stimulus_frames` / stimulus join:

- Read `trial_start_frame` from trial attrs.
- Map `src_run = absolute_frame - trial_start_frame` for `motor_fb`.
- Only sample duty when xy `trial_state == run` (or `src_run >= 0`).
- Read `dist_to_exit_px` from xy at **absolute** index (no min-truncate with motor).

### B. Fix at legacy import (correct storage)

On init/sync, either:

- Pass **full-length** `w,m` with `trial_start_frame` to `write_feedback_series` so `frame_index` is absolute and ITI rows are `iti_wait`; or
- Keep run-only storage but set `feedback.attrs["run_start_frame"] = trial_start_frame` and `frame_index = arange(run_start, run_start+n)`.

### C. Fix in `process_trial` (canonical for re-run cohort)

After xy is built, expand feedback to full `n_frames`:

- ITI/excluded rows: `motor_fb = fixed ITI duty` or NaN.
- Run rows: copy from run-only feedback at `run_row + i`.
- Write unified `feedback/table` matching xy `frame_index`.

### D. One-time migration

`maze-reprocess-controller-h5` or legacy_db subcommand to rewrite `feedback/table` on existing `vast_results_legacy.h5` without re-running SLEAP.

**Recommendation:** **A** immediately for stimulus MI; **C + D** for durable schema alignment.

## Scripts

- `compare_indexing.py` — direct vs offset motor lookup
- `../2026-07-08-stimulus-end-bout-gaps/probe_feedback_frame_index.py` — trial attr / state counts
- `../2026-07-08-stimulus-end-bout-gaps/cohort_feedback_gap.py` — cohort xy−feedback length gap

## Conclusions

Empty tail stimulus values are not mysterious missing data — they are where **absolute kpMS frame index exceeds run-only feedback length**. The deeper issue is **coordinate system mismatch**: feedback was stored run-relative to avoid ITI redundancy, but xy and kpMS alignment use absolute video indices. Frame index in the feedback table is **not inaccurate internally** (0…n_run−1); it is **not comparable to xy `frame_index`** without subtracting `trial_start_frame`.

Duty values in `stimulus_bout_features.csv` for legacy cohort should be treated as **misaligned until read path is fixed**; distance is closer to correct but truncated at feedback length.
