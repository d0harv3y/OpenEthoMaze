# Handoff: stimulus MI when-coupling (grill closed)

Date: 2026-07-09. Mode: design locked; **implemented** (2026-07-09).

## What closed

Grill on “when is coupling real (sessions/trials) and does that differ by strata?”

**Authoritative plan:** [`.cursor/plans/stimulus_mi_when_coupling.plan.md`](../../.cursor/plans/stimulus_mi_when_coupling.plan.md)

**ADR:** [`docs/adr/0006-stimulus-mi-trial-trajectory-not-mixed.md`](../adr/0006-stimulus-mi-trial-trajectory-not-mixed.md)

## One-line answer

Trial-level MI + `trial_ord` trajectories → per-animal slope and early−late delta → Mann–Whitney/Kruskal across sex/strain/tx; pooled animal MI stays.

## Teaching note

Lesson [`teach/mutual-information/lessons/0004-slope-of-mi-vs-trial.html`](../../teach/mutual-information/lessons/0004-slope-of-mi-vs-trial.html) covers `mi_mm` vs excess slopes (grill Q11).

## Do not relitigate

See plan table. Especially: no mixed model; primary when-tests = run×duty|dist×occupancy; full factorial in `mi_per_trial.csv`; `--per-trial` additive to pooled.

## Parallel (not this plan)

User edited duty bin edges (inserted 40) and is re-running `maze-compute-stimulus-mi` on the pooled path — orthogonal to when-coupling implementation.

## First build step when asked

Extend `stimulus_mi.py` / `maze-compute-stimulus-mi` with `--per-trial` (no nulls first); emit `mi_per_trial.csv` + summaries; then `--trial-nulls` and `group_mi_when_tests.csv`.
