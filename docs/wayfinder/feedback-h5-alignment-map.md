# Wayfinder map: feedback H5 alignment

Label: `wayfinder:map`

## Destination

`feedback/table` in pipeline H5 (including `vast_results_legacy.h5`) shares the **absolute video timeline** with `ambulation_metrics/*/xy`: same row count, matching `frame_index`, `trial_state` bands copied from xy, run-phase `motor_fb`/`light_fb` at correct indices. Stimulus join and downstream tools index duty by absolute frame without offset hacks.

## Notes

- Investigation: `scratch/2026-07-08-feedback-h5-integration/README.md`
- Skills: TDD for alignment lib; run `maze-align-feedback-h5` on cohort after merge
- Controller acquisition (`recording.py`) already writes aligned tables; fix targets legacy import + pipeline run + migration

## Decisions so far

- [**Align feedback table library + tests**](docs/wayfinder/feedback-h5-alignment-map.md) — `maze/pipeline/db/feedback_align.py`: detect run-relative vs absolute; expand or reindex to xy `frame_index`; `feedback_table_matches_xy` contract.
- [**Legacy import writes full-timeline feedback**](docs/wayfinder/feedback-h5-alignment-map.md) — `legacy_db init/sync` passes full `w/m` with `trial_start_frame` (no `w[start:]` slice).
- [**Pipeline run materializes aligned feedback**](docs/wayfinder/feedback-h5-alignment-map.md) — `process_trial` calls `align_feedback_for_trial` after xy write.
- [**One-time `maze-align-feedback-h5` CLI**](docs/wayfinder/feedback-h5-alignment-map.md) — batch rewrite in place; `--dry-run` for counts.
- [**Stimulus join reads aligned tables**](docs/wayfinder/feedback-h5-alignment-map.md) — `read_trial_stimulus_frames` expands on read if needed; verify checks `feedback_aligned`.

## Not yet specified

- Whether ITI `motor_fb` on legacy trials should be backfilled from source full `w/m` or left NaN outside run when only run-relative data exists
- Incongruence QC in `process_trial` after alignment (may still use analysis-window slice)

## Out of scope

- Re-running SLEAP / full `maze-legacy-db run` on the cohort
- kpMS alignment changes

## Frontier tickets

| Ticket | Type | Blocks | Question |
|--------|------|--------|------------|
| **Align feedback table library + tests** | task/AFK | — | What is the canonical `align_feedback_to_xy` API and detection rules for run-relative vs absolute legacy tables? |
| **Legacy import writes full-timeline feedback** | task/AFK | Align lib | Should `legacy_db init/sync` pass full `w/m` with `trial_start_frame` instead of slicing? |
| **Pipeline run materializes aligned feedback** | task/AFK | Align lib | Where in `process_trial` do we rewrite `feedback/table` after xy is written? |
| **One-time `maze-align-feedback-h5` CLI** | task/AFK | Align lib | How do we batch-rewrite an existing H5 in place? |
| **Stimulus join reads aligned tables** | task/AFK | Align lib | What verification does `maze-join-stimulus-bouts` need once tables are fixed? |
