# Empty stimulus values at end-of-trial bouts

## Task

Explain why `stimulus_bout_features.csv` has many empty `bout_mean_duty` / `bout_mean_dist_px` values, concentrated at the **end** of trials, in the gerstner_vast_fit cohort.

## Background

- Join CLI: `maze-join-stimulus-bouts` maps kpMS bout row spans → source video frames → mean `feedback/table.motor_fb` and `ambulation_metrics/*/xy.dist_to_exit_px`.
- Cohort artifacts: `C:\Users\admin\Documents\work\sack\gerstner_vast_fit\behavior_ethogram\stimulus_mi\`
- Tracking H5 used at join: `vast_results_legacy.h5` (per `join_stimulus_bouts_summary.json`)
- Empty cells = `mean_scalar_over_rows` returned NaN → written as blank (no in-range finite stimulus samples for that bout's kpMS rows).

## Checklist

- [x] Quantify empty rate and spatial pattern in CSV
- [x] Trace join logic for NaN conditions
- [x] Compare kpMS alignment length vs stimulus array length (sample trial)
- [x] Cohort-wide feedback vs xy table length gap
- [x] Document root cause and implications for MI

## Findings

### CSV pattern (`analyze_empty_stimulus.py`)

| Metric | Value |
|--------|-------|
| Total bouts | 199,321 |
| Empty stimulus bouts | 21,075 (**10.57%**) |
| Trials with any empty | 1,753 / 1,840 |
| Empty only in trial tail | **1,750 / 1,753** |
| Mean bout_index fraction (empty rows) | 0.896 |
| Mean row_end fraction (empty rows) | 0.919 |

Empty bouts are almost always a **suffix** of each trial's bout sequence — not scattered gaps.

By phase: 20,620 `run`, 455 `iti_wait` (tail empties are mostly still labeled `run`).

Example `3245-S01-T01`: bouts through row ~3346 have duty/dist; bouts from row 3346→3598 are empty.

### Sample trial probe (`probe_alignment_vs_stimulus.py`, trial `3245-S01-T01`)

| Timeline | Length (frames/rows) |
|----------|----------------------|
| kpMS syllable / aligned rows | 3,598 |
| `source_frame_indices` range | 0 … 3,599 |
| `results.h5` syllable | 3,598 (matches alignment) |
| `ambulation_metrics/spot` xy | **3,600** |
| `feedback/table` (motor_fb) | **3,323** |
| Stimulus reader effective length | **3,323** (`min(motor_fb, dist)`) |

- **277 kpMS rows (7.7%)** have `source_frame_index >= 3323` → no valid motor_fb index.
- First out-of-range kpMS row: index 3321 → `src=3323`.
- Last 10 source indices: 3590…3599 (pose timeline continues; feedback does not).

### Cohort-wide (`cohort_feedback_gap.py`, 1,993 trials with both tables)

- **92.2%** of trials: xy table longer than `feedback/table`.
- Gap `len(xy) - len(feedback)`: **median 275 frames** (~9.2 s @ 30 Hz), max 3,002.
- This is structural in legacy VAST H5, not a join averaging bug.

### Mechanism (code path)

```text
compile bout_features  →  row_start/row_end index kpMS-aligned rows (pose timeline)
join_stimulus_bouts    →  src = source_frame_indices[row_start:row_end)
                         →  keep only src where 0 <= src < len(stimulus)
read_trial_stimulus_frames → len = min(len(motor_fb), len(dist))
                         →  capped by shorter feedback table
```

When the trial's pose/kpMS timeline extends past the end of `feedback/table`, **tail bouts have no mappable stimulus** → blank CSV cells.

Duty and dist are blank together because both go through the same row→frame map and the reader truncates to `min(feedback, dist)`; here **feedback is the binding shorter series** (xy actually extends further).

### What it is NOT

- Not random missing values mid-trial (only 3 mixed trials).
- Not alignment cache failure (1,840/1,993 trials joined; 0 alignment skips).
- Not unmapped trials (those were dropped at join — 153 manifest misses).

## Conclusions

**Root cause:** Legacy cohort H5 has a systematic **timeline mismatch** — anatomical pose / kpMS alignment runs ~250+ frames longer than `feedback/table.motor_fb` at trial end. Tail syllable bouts still exist in `bout_features.csv` but point at source frames with no feedback row.

**Impact on MI:** ~10.6% of bouts carry no stimulus. They will drop out of bin assignment (empty → skipped) or dilute per-animal counts. Tail `run` bouts labeled empty are **not** “no stimulus by design” — they are **missing acquisition/import coverage**, distinct from the planned `iti` negative control (fixed duty where data exists).

**Recommended next steps (product, not done here):**

1. **Analysis filter:** exclude bouts where `bout_mean_duty` or `bout_mean_dist_px` is blank before MI (or require ≥1 finite frame per bout).
2. **Join improvement:** read duty and dist at **independent** lengths (dist from full xy even when feedback is shorter); still NaN for duty-only tail.
3. **Data QC:** report per-trial `n_kpms_rows`, `n_feedback_rows`, `n_oob_rows` in join summary.
4. **Longer term:** backfill or truncate kpMS timeline to feedback coverage for legacy imports.

Scripts in this folder: `analyze_empty_stimulus.py`, `probe_alignment_vs_stimulus.py`, `cohort_feedback_gap.py`.
