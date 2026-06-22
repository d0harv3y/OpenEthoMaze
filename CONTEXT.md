# OpenEthoMaze — dwell averaging

Analysis context for pooling RUN-phase dwell heatmaps across animals and trial blocks in the legacy VAST database.

## Language

**Dwell average**:
Mean dwell time (seconds per pixel) computed by building per-trial dwell grids from RUN-phase trajectories, averaging those grids in seconds-space, then rendering one heatmap.
_Avoid_: Pixel-averaging stored composite PNGs, colormap averaging

**Trial block**:
A within-session trial unit for averaging: T01–T03, T04–T06, T07–T09, or the full session T01–T09 (`1-9`).
_Avoid_: Session, phase

**Block average**:
Per animal, mean the dwell grids of that animal's trials in the block; then mean those per-animal grids across animals in the stratum.
_Avoid_: Pooling all trials directly, trial-weighted average

**Partial block**:
An animal×session may contribute to a block average when at least one trial in that block is present; the per-animal mean uses only available trials.
_Avoid_: Require all three trials, drop on any missing trial

**Arena-normalized dwell grid**:
Dwell accumulated on a fixed cm grid relative to each trial's arena center (not raw QC image pixels), so trials with different calibrations can be averaged.
_Avoid_: Image-pixel averaging, exit-aligned frame

**Block dwell export**:
PNG mean-dwell plots plus a `summary.csv` row per file (`n_animal_sessions`, `n_unique_animals`, `n_trials`, strata keys). Colorbar fixed at 4.0 s (`MAX_DWELL_TIME_S`).
_Avoid_: Per-plot auto scale, H5-only output

**Cross-session pool**:
Dwell averages that collapse S01–S05 into one plot per stratum and trial block; each animal×session pair counts equally.
_Avoid_: Per-session export, animal-only pooling across sessions

**Export path**:
`{out}/S##/{tx}/S##_tx_strain_sex_trial{lo}-{hi}.png` — session and treatment as folders; full stratum and trial block in the filename.
_Avoid_: Flat output directory, block-only filenames

**Exit ensemble overlay**:
On each group-average plot, draw every contributing trial's exit zone (arena-normalized cm); translucent fills so all exits remain visible over the heatmap.
_Avoid_: Single mean exit, exit-aligned averaging frame

**Stratum**:
A subgroup defined by the cross of sex, strain, and treatment (`tx`) labels from the trial manifest.
_Avoid_: Cohort, group, condition (unless referring to manifest `cohort` column)

**Dwell source**:
RUN-phase `spot_hybrid` XY from `ambulation_metrics` in the legacy H5, filtered to `trial_state == 'run'`.
_Avoid_: SLEAP re-read, all-node heatmap, centroid, in-range

**Experimental session**:
An ordinal within-animal session label `S01`–`S05` with `phase == experimental` in the trial manifest.
_Avoid_: Habituation session (`hS*`), pilot session (`S00`)

**Ele cohort**:
Trials whose manifest `researcher` is exactly `Emma|Hayden` — the experimental dataset scope for this analysis.
_Avoid_: All researchers, separate Emma/Hayden labels, habituation
