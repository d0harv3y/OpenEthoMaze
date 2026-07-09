# Stimulus ↔ syllable MI contract (pilot)

Schema ids: **`stimulus_join_v1`**, **`stimulus_mi_v1`**.

Authority:
- [`stimulus_join_contract.py`](../maze/kpms/behavior_ethogram/stimulus_join_contract.py)
- [`stimulus_mi_contract.py`](../maze/kpms/behavior_ethogram/stimulus_mi_contract.py)

Implementation:
- [`stimulus_join.py`](../maze/kpms/behavior_ethogram/stimulus_join.py)
- [`stimulus_mi.py`](../maze/kpms/behavior_ethogram/stimulus_mi.py)

CLIs: `uv run maze-join-stimulus-bouts`, `uv run maze-compute-stimulus-mi`.

## Confound (report in all outputs)

Stimulus duty is a **deterministic function of distance-to-exit**. Mutual information therefore conflates "response to delivered stimulus" with "response to goal proximity." No probe/omission trial exists in this cohort. The `iti` phase (fixed duty) is a partial negative control; duty-vs-distance divergence is a partial saturation check only.

## Artifact locations

```
<kpms_root>/behavior_ethogram/stimulus_mi/
  stimulus_bout_features.csv
  stimulus_bin_edges.json
  mi_per_animal.csv
  group_mi_tests.csv
  mi_per_trial.csv
  mi_trial_animal_summaries.csv
  group_mi_when_tests.csv
  join_stimulus_bouts_summary.json
  compute_stimulus_mi_summary.json
```

Path helpers: `stimulus_mi_dir`, `stimulus_bout_features_csv`, `stimulus_bin_edges_json`, `mi_per_animal_csv`, `group_mi_tests_csv`, `mi_per_trial_csv`, `mi_trial_animal_summaries_csv`, `group_mi_when_tests_csv`.

**When-coupling (shipped):** per-trial MI + ordinal exposure summaries — see [`.cursor/plans/stimulus_mi_when_coupling.plan.md`](../.cursor/plans/stimulus_mi_when_coupling.plan.md) and [ADR-0006](adr/0006-stimulus-mi-trial-trajectory-not-mixed.md). Enable with `--per-trial`; optional `--trial-nulls` for circular nulls per trial.

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
| `null_circ_mean`, `null_circ_p`, `excess` | Populated only with `--trial-nulls` (circular, n_perm=200) |

Optional gates: `--min-run-bouts`, `--min-h-stim` (off by default).

## Stage 6 — `mi_trial_animal_summaries.csv`

Per animal × phase × stim_var × mi_type trajectory scalars from per-trial rows:

| Column | Description |
|--------|-------------|
| `n_trials`, `mean_mi_mm`, `median_mi_mm`, `mean_n_bouts`, `mean_H_stim` | Descriptive |
| `slope_vs_trial_ord` | OLS slope of `mi_mm` ~ `trial_ord` |
| `early_late_delta` | mean(first k=3 trials) − mean(last k=3); requires N ≥ 6 |
| `slope_vs_excess`, `early_late_delta_excess`, `null_clear_fraction` | With `--trial-nulls` only |

## Stage 7 — `group_mi_when_tests.csv`

Mann–Whitney/Kruskal on animal-level when metrics. **Primary cells only:** `run × {duty, dist} × occupancy`.

| Column | Description |
|--------|-------------|
| `factor`, `level_a`, `level_b` | Grouping |
| `phase`, `stim_var`, `mi_type` | Slice keys |
| `metric` | `slope_vs_trial_ord`, `early_late_delta`, or excess twins when nulls on |
| `n_a`, `n_b`, `median_a`, `median_b`, `stat`, `p`, `test` | Same as Stage 4 |
