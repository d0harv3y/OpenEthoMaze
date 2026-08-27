# Stimulus ↔ syllable MI contract (pilot)

Schema ids: **`stimulus_join_v1`**, **`stimulus_mi_v1`**.

Authority:
- [`stimulus_join_contract.py`](../maze/kpms/behavior_ethogram/stimulus_join_contract.py)
- [`stimulus_mi_contract.py`](../maze/kpms/behavior_ethogram/stimulus_mi_contract.py)

Implementation:
- [`stimulus_join.py`](../maze/kpms/behavior_ethogram/stimulus_join.py)
- [`stimulus_mi.py`](../maze/kpms/behavior_ethogram/stimulus_mi.py)

CLIs: `uv run maze-join-stimulus-bouts`, `uv run maze-compute-stimulus-mi`.

**Column-level data dictionary (all tables):** [`stimulus_mi_data_dictionary.md`](stimulus_mi_data_dictionary.md).

## Confound (report in all outputs)

Stimulus duty is a **deterministic function of distance-to-exit**. Mutual information therefore conflates "response to delivered stimulus" with "response to goal proximity." No probe/omission trial exists in this cohort. The `iti` phase is a partial negative control; duty-vs-distance divergence is a partial saturation check only.

### ITI negative control — duty vs distance

| Phase | `stim_var` | Expected MI | If null is cleared |
|-------|------------|-------------|-------------------|
| `iti` | **duty** | ~chance (duty fixed off-center during `iti_wait`) | Suspect join bug or mis-phase labeling |
| `iti` | **dist** | **May exceed null** | **Expected under chamber geometry**, not a failed control |

During `iti_wait`, delivered duty is often flat (see `wait_not_center_duty_pct` in VAST config), but **`dist_to_exit_px` still varies systematically**: the exit is placed opposite the animal's start position, so distance evolves as the animal moves through the wait. Bout-level syllable occupancy can track distance bin along that trajectory even when no stimulus signal is being manipulated. Circular-shift null breaks bout pairing but does not remove this trial-wide spatial co-structure.

**Interpretation:** `iti_control_flag=1` with `stim_var=dist` means **distance MI is measuring goal/chamber geometry + locomotion**, not independent vibration coupling. Do not treat ITI×dist as evidence of stimulus-driven behavior. Use **ITI×duty** as the clean control; quarantine ITI×dist from primary inference and apply the same caution to **run×dist** (duty and distance are coupled in run as well).

## Artifact locations

```
<kpms_root>/behavior_ethogram/stimulus_mi/
  stimulus_bout_features.csv
  stimulus_bin_edges.json
  mi_per_animal.csv
  group_mi_tests.csv
  group_mi_excess_tests.csv
  mi_per_trial.csv
  mi_trial_animal_summaries.csv
  group_mi_when_tests.csv
  group_mi_sliced_tests.csv
  join_stimulus_bouts_summary.json
  compute_stimulus_mi_summary.json
```

Path helpers: `stimulus_mi_dir`, `stimulus_bout_features_csv`, `stimulus_bin_edges_json`, `mi_per_animal_csv`, `group_mi_tests_csv`, `group_mi_excess_tests_csv`, `mi_per_trial_csv`, `mi_trial_animal_summaries_csv`, `group_mi_when_tests_csv`, `group_mi_sliced_tests_csv`.

**When-coupling (shipped):** per-trial MI + ordinal exposure summaries — see [`.cursor/plans/stimulus_mi_when_coupling.plan.md`](../.cursor/plans/stimulus_mi_when_coupling.plan.md) and [ADR-0006](adr/0006-stimulus-mi-trial-trajectory-not-mixed.md). Enable with `--per-trial`; optional `--trial-nulls` for circular nulls per trial.

**Sliced strata + within-session early/late (shipped):** [`.cursor/plans/stimulus_mi_sliced_factorial.plan.md`](../.cursor/plans/stimulus_mi_sliced_factorial.plan.md). Enable with `--sliced-tests` (requires `--per-trial`).

## Stage 1 — `stimulus_bout_features.csv`

Join of `stage_ii/bout_features.csv` bout identity/strata with per-bout stimulus means from trial H5:

| Column | Units | Description |
|--------|-------|-------------|
| *(bout identity + strata)* | | Same columns as `BOUT_TABLE_FIELDS` identity subset through `bout_primary_state`. |
| `bout_mean_duty` | 0–1 | Mean `feedback/table.motor_fb` over bout kpMS rows. |
| `bout_mean_dist_px` | px | Mean `ambulation_metrics/*/xy.dist_to_exit_px` over bout kpMS rows. |

Cohort filters (CLI defaults): `experiment ∈ {VASTcont, VASTalt}`, drop `?`/blank strain and blank sex, optional `--tx`. Strains after drop must be `wt` or `tg`.

## Stage 2 — `stimulus_bin_edges.json`

Global fixed quantile edges (`--n-bins`, default 4) fit on **run-phase** bouts across the filtered cohort, separately for duty and distance. Reused when the sidecar exists.

## Stage 3 — `mi_per_animal.csv`

Per animal × phase (`run`, `iti`) × stim_var (`duty`, `dist`) × mi_type (`occupancy`, `transition`):

| Column | Description |
|--------|-------------|
| `animal_id`, `sex`, `strain`, `tx` | Stratification |
| `phase`, `stim_var`, `mi_type` | Slice keys |
| `n_bouts` | Bout count in slice |
| `H_stim`, `H_syll` | Marginal entropies (bits) |
| `mi_raw` | Plug-in MI (bits) |
| `mi_mm` | Miller–Madow corrected MI (bits) |
| `null_circ_mean`, `null_circ_p` | Circular shift null (primary) |
| `null_perm_mean`, `null_perm_p` | Bin-label permutation null |
| `excess` | `mi_mm − null_circ_mean` (bits) |
| `iti_control_flag` | 1 when iti `mi_mm` clears circular null (possible confound/bug) |

**Occupancy:** `I(syllable ; stim_bin)`. **Transition:** `I(next_syllable ; stim_bin | current_syllable)` on consecutive bout pairs within trial.

## Stage 4 — `group_mi_tests.csv`

Per-animal `mi_mm` compared across `sex`, `genotype` (= `strain`), or `tx`:

| Column | Description |
|--------|-------------|
| `factor`, `level_a`, `level_b` | Grouping (`(all)` for Kruskal) |
| `phase`, `stim_var`, `mi_type` | Slice keys |
| `n_a`, `n_b`, `median_a`, `median_b` | Sample sizes / medians |
| `stat`, `p` | `mannwhitneyu` (2 levels) or `kruskal` (>2) |
| `test` | Test name |

## Stage 4b — `group_mi_excess_tests.csv`

Same schema as `group_mi_tests.csv`, but Mann–Whitney/Kruskal on per-animal **`excess`** (`mi_mm − null_circ_mean`) — coupling beyond the circular null.

## Stage 5 — `mi_per_trial.csv` (`--per-trial`)

Per animal × trial × phase × stim_var × mi_type (full factorial). Ordinal exposure columns support trajectory summaries.

| Column | Description |
|--------|-------------|
| `animal_id`, `sex`, `strain`, `tx` | Stratification |
| `session`, `trial`, `trial_key` | Trial identity |
| `trial_ord` | 0-based chronological index within animal (parsed from session/trial suffixes) |
| `cum_run_bouts` | Running sum of run-phase bouts through this trial (inclusive) |
| `phase`, `stim_var`, `mi_type` | Slice keys |
| `n_bouts`, `H_stim`, `H_syll`, `mi_raw`, `mi_mm` | Same semantics as pooled rows |
| `null_circ_mean`, `null_circ_p`, `excess` | Populated only with `--trial-nulls` (circular; uses `--n-perm`, default 1000) |

Optional gates: `--min-run-bouts`, `--min-h-stim` (off by default).

## Stage 6 — `mi_trial_animal_summaries.csv`

Per animal × phase × stim_var × mi_type trajectory scalars from per-trial rows:

| Column | Description |
|--------|-------------|
| `n_trials`, `mean_mi_mm`, `median_mi_mm`, `mean_n_bouts`, `mean_H_stim` | Descriptive |
| `slope_vs_trial_ord` | OLS slope of `mi_mm` ~ `trial_ord` |
| `early_late_delta` | mean(first k=3 trials) − mean(last k=3); requires N ≥ 6 |
| `slope_vs_excess`, `early_late_delta_excess`, `null_clear_fraction` | With `--trial-nulls` only |
| `early_late_delta_within_session` | mean of per-session early−late deltas (k=3, N_sess ≥ 6) |
| `early_late_delta_within_session_excess` | excess twin when `--trial-nulls` |
| `n_sessions_used` | Sessions contributing a within-session delta |

## Stage 7 — `group_mi_when_tests.csv`

Mann–Whitney/Kruskal on animal-level when metrics. **Primary cells only:** `run × {duty, dist} × occupancy`.

BH-FDR (`q_bh`) is computed separately within families **B** and **C** (same endpoints as Stage 8):

| Family | Metric |
|--------|--------|
| B | `slope_vs_excess` if `--trial-nulls`, else `slope_vs_trial_ord` |
| C | career `early_late_delta` (excess twin when nulls) |

| Column | Description |
|--------|-------------|
| `factor`, `level_a`, `level_b` | Grouping |
| `phase`, `stim_var`, `mi_type` | Slice keys |
| `metric` | `slope_vs_trial_ord`, `early_late_delta`, or excess twins when nulls on |
| `n_a`, `n_b`, `median_a`, `median_b`, `stat`, `p`, `q_bh`, `test` | Test output |

When `--trial-nulls` is on, raw slope/delta metrics are also emitted with `p` but **no** `q_bh` (exploratory).

## Stage 8 — `group_mi_sliced_tests.csv` (`--sliced-tests`)

One-hold and two-hold simple-effect Mann–Whitney tests on primary cells (`run × {duty, dist} × occupancy`). Both arms must have **n ≥ 5** or the row is omitted. BH-FDR (`q_bh`) is computed separately within each family:

| Family | Metric |
|--------|--------|
| A | pooled `mi_mm` |
| B | `slope_vs_excess` if `--trial-nulls`, else `slope_vs_trial_ord` |
| C | career `early_late_delta` (excess twin when nulls) |
| D | `early_late_delta_within_session` (excess twin when nulls) |

| Column | Description |
|--------|-------------|
| `fdr_family` | A, B, C, or D |
| `hold_sex`, `hold_strain`, `hold_tx` | Strata held fixed (blank = not held) |
| `contrast_factor`, `level_a`, `level_b` | Simple effect contrast |
| `phase`, `stim_var`, `mi_type`, `metric` | Slice keys |
| `n_a`, `n_b`, `median_a`, `median_b`, `stat`, `p`, `q_bh`, `test` | Test output |

When `--trial-nulls` is on, raw slope/delta metrics are also emitted with `p` but **no** `q_bh` (exploratory).
