# Handoff: stimulus MI sliced tests + within-session early/late

Date: 2026-07-09. Mode: design locked; **implemented** (2026-07-09).

## Authoritative plan

[`.cursor/plans/stimulus_mi_sliced_factorial.plan.md`](../../.cursor/plans/stimulus_mi_sliced_factorial.plan.md)

Related: when-coupling [`.cursor/plans/stimulus_mi_when_coupling.plan.md`](../../.cursor/plans/stimulus_mi_when_coupling.plan.md) (career clock already shipped).

## One-line

One-hold + two-hold simple effects across sex/strain/tx on primary run-occupancy scalars; BH in four families; add mean within-session early−late alongside career early−late.

## Do not relitigate

See plan table. Especially: two-hold is not redundant with one-hold; full catalog equal within FDR families; excess metrics own the when FDR slots when `--trial-nulls` is on; no per-session pooled MI in this slice.

## First build step when asked

1. `early_late_delta_within_session` (+ excess) on `compute_trial_animal_summaries`
2. `--sliced-tests` catalog + `group_mi_sliced_tests.csv` + BH families A–D
