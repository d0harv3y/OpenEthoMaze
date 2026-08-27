# Stimulus MI (mutual information) — data dictionary

Schemas: **`stimulus_join_v1`**, **`stimulus_mi_v1`**.  
Authority: [`stimulus_join_contract.py`](../maze/kpms/behavior_ethogram/stimulus_join_contract.py), [`stimulus_mi_contract.py`](../maze/kpms/behavior_ethogram/stimulus_mi_contract.py).  
Pipeline overview: [`stimulus_mi_contract.md`](stimulus_mi_contract.md).

**Abbreviations** (spelled out once here; shorthand in tables below):

- **KL** / **D_KL** — Kullback–Leibler divergence; **H(·)** — Shannon entropy
- **kpMS** — keypoint-MoSeq (per-frame pose syllable rows)
- **ITI** / **`iti`** — inter-trial interval (`iti_wait` bouts, mapped to `iti` in MI tables)
- **MLE** — maximum-likelihood estimate; **OLS** — ordinary least squares (linear regression)
- **FDR** — false discovery rate; **BH** — Benjamini–Hochberg correction
- **PWM** — pulse-width modulation; **px** — pixels
- **CLI** — command-line interface; **NaN** — not a number; **QC** — quality control
- **Mann–Whitney** / **Kruskal** — Mann–Whitney U / Kruskal–Wallis tests
- **`wt`** / **`tg`** — wild-type / transgenic genotype
- **ADR** — architecture decision record

**Cohort path (this run):**  
`<kpms_root>/behavior_ethogram/stimulus_mi/` under `gerstner_vast_fit`.  
Command that produced the full set:  
`uv run maze-compute-stimulus-mi --kpms-root … --per-trial --sliced-tests --trial-nulls`

**Confound (all MI tables):** delivered duty is a deterministic function of distance-to-exit; mutual information *I* conflates stimulus response with goal proximity. **ITI control:** use `iti × duty` as the clean negative control; `iti × dist` may clear the null because distance varies systematically during `iti_wait` (exit opposite start) — see [contract § Confound](stimulus_mi_contract.md#confound-report-in-all-outputs).

**What *I* is:**

```
I(syll; stim_bin) = D_KL( P(joint) || P(syll) P(stim) )
                  = H(syll) − H(syll | stim)
```

Units: bits (log₂). Not KL divergence between the two marginals alone.

---

## Artifact map

| File | Grain | Rows (this run) | CLI (command-line) flags |
|------|-------|-----------------|-----------|
| `stimulus_bout_features.csv` | 1 bout | ~199k | `maze-join-stimulus-bouts` |
| `stimulus_bin_edges.json` | cohort codebook | 1 object | written once / reused |
| `mi_per_animal.csv` | animal × phase × stim × mi_type | 328 (= 41×2×2×2) | always |
| `group_mi_tests.csv` | marginal group test on `mi_mm` | 24 | always |
| `group_mi_excess_tests.csv` | marginal group test on `excess` | 24 | always |
| `mi_per_trial.csv` | animal × trial × … | 14701 | `--per-trial` |
| `mi_trial_animal_summaries.csv` | animal × phase × stim × mi_type | 328 | `--per-trial` |
| `group_mi_when_tests.csv` | marginal when-metric test | 12 or 24 | `--per-trial` (± `--trial-nulls`) |
| `group_mi_sliced_tests.csv` | sliced simple-effect test | 192 or 336 | `--sliced-tests` |
| `join_stimulus_bouts_summary.json` | run metadata | 1 | join |
| `compute_stimulus_mi_summary.json` | run metadata | 1 | compute |

---

## Shared vocab (slice keys)

| Field | Allowed values | Meaning |
|-------|----------------|---------|
| `phase` **(MI tables)** | `run`, `iti` | From bout majority state: `run` vs `iti_wait` (mapped to `iti`). **Not** the manifest column also named `phase`. |
| `stim_var` | `duty`, `dist` | Stimulus scalar → global bins |
| `mi_type` | `occupancy`, `transition` | `I(syll; stim)` vs `I(next; stim | current)` |
| `sex` | `F`, `M` | |
| `strain` | `wt`, `tg` | Genotype (wild-type / transgenic); group tests label factor `genotype` |
| `tx` | `RBSF-1`, `n/a` (blank→`n/a`) | Treatment |

**Primary analysis cells** (when-tests + sliced-tests):  
`phase=run` ∧ `mi_type=occupancy` ∧ `stim_var ∈ {duty, dist}`.

---

## 1. `stimulus_bout_features.csv`

One row = one syllable **bout** with mean stimulus over its kpMS rows.

### Identity / strata

| Column | Type | Description |
|--------|------|-------------|
| `stream` | str | Pose stream (e.g. `anatomical`) |
| `seed` | str | kpMS apply / fit id |
| `trial_key` | str | Unique trial id (e.g. `3245-S01-T01`) |
| `animal_id` | str | Subject |
| `session` | str | Session label (`S01`…`S05`) |
| `trial` | str | Trial within session (`T01`…) |
| `phase` | str | **Manifest** phase (here: `experimental`) — not MI `run`/`iti` |
| `exit_number` | str/int | Exit id from manifest |
| `sex`, `strain`, `tx` | str | Strata |
| `experiment` | str | e.g. `VASTcont`, `VASTalt` |
| `drug`, `cohort`, `researcher` | str | Manifest labels (may be blank) |
| `is_habituation` | 0/1 | Habituation trial flag |
| `raw_syllable_id` | int | kpMS syllable id for this bout |
| `bout_index` | int | 0-based bout index within trial |
| `row_start` | int | Inclusive kpMS row index |
| `row_end_exclusive` | int | Exclusive end row |
| `bout_frames` | int | `row_end_exclusive - row_start` |
| `bout_duration_s` | float | Duration (s) |
| `bout_primary_state` | str | Majority legacy trial state in bout (`run`, `iti_wait`, …) |

### Stimulus scalars

| Column | Units | Description |
|--------|-------|-------------|
| `bout_mean_duty` | PWM (pulse-width modulation) units (cohort ~0–227; **not** strictly 0–1) | Mean `feedback/table.motor_fb` over bout rows |
| `bout_mean_dist_px` | px (pixels) | Mean `xy.dist_to_exit_px` over bout rows |

---

## 2. `stimulus_bin_edges.json`

Global stimulus codebook. Interior edges define bins via `numpy.digitize` (left-closed / right-open style as in `assign_bins`).

| Key | Description |
|-----|-------------|
| `n_bins` | Declared bin count (this cohort: **5** for both after manual edit) |
| `duty_edges` | Length `n_bins+1`; first/last ±∞. This cohort: −∞, **40**, 50, 64, 74, ∞ |
| `dist_edges` | Same. This cohort: −∞, **80**, 111.14…, 170.36…, 202.41…, ∞ |
| `edge_notes` | Optional human notes on manual splits |

Duty/dist may be asymmetric if edited by hand; MI still uses whatever edges are loaded.

---

## 3. `mi_per_animal.csv`

One row = one animal’s **pooled** MI for one `(phase, stim_var, mi_type)` cell (all that animal’s trials pooled).

| Column | Units | Description |
|--------|-------|-------------|
| `animal_id`, `sex`, `strain`, `tx` | | Strata |
| `phase`, `stim_var`, `mi_type` | | Slice keys (MI `phase`) |
| `n_bouts` | count | Bouts in this cell |
| `H_stim` | bits | Marginal entropy of stim bins |
| `H_syll` | bits | Marginal entropy of syllables (or next-syll for transition setup) |
| `mi_raw` | bits | Plug-in / MLE (maximum-likelihood estimate) MI (upward biased) |
| `mi_mm` | bits | Miller–Madow corrected MI (**primary pooled endpoint**) |
| `null_circ_mean` | bits | Mean MI under circular within-trial stim shifts |
| `null_circ_p` | [0,1] | Right-tail p vs circular null (primary) |
| `null_perm_mean` | bits | Mean under bin-label permutation |
| `null_perm_p` | [0,1] | Right-tail p vs permutation (loose) |
| `excess` | bits | `mi_mm − null_circ_mean` |
| `iti_control_flag` | 0/1 | 1 if `phase=iti` and `mi_mm` clears circular null — treat as warning (esp. `stim_var=dist`) |

---

## 4. `group_mi_tests.csv`

Marginal Mann–Whitney U (2 levels) or Kruskal–Wallis (>2) on **per-animal `mi_mm`**. One scalar per animal → no trial pseudoreplication.

| Column | Description |
|--------|-------------|
| `factor` | `sex`, `genotype` (=strain), or `tx` |
| `level_a`, `level_b` | Compared levels (`(all)` if Kruskal–Wallis) |
| `phase`, `stim_var`, `mi_type` | Full factorial (includes iti) |
| `n_a`, `n_b` | Animals per arm |
| `median_a`, `median_b` | Median `mi_mm` |
| `stat`, `p` | Test statistic and p-value |
| `test` | `mannwhitneyu` or `kruskal` |

---

## 4b. `group_mi_excess_tests.csv`

Same columns as §4. Mann–Whitney U / Kruskal–Wallis on per-animal **`excess`** (`mi_mm − null_circ_mean`). Medians are excess (bits), not raw `mi_mm`.

---

## 5. `mi_per_trial.csv` (`--per-trial`)

One row = MI for one trial in one `(phase, stim_var, mi_type)` cell. Full factorial.

| Column | Units | Description |
|--------|-------|-------------|
| `animal_id`, `sex`, `strain`, `tx` | | Strata |
| `session`, `trial`, `trial_key` | | Trial identity |
| `trial_ord` | int ≥0 | Career order within animal (parsed numeric session/trial suffixes) |
| `cum_run_bouts` | count | Cumulative run-phase bouts through this trial (inclusive) |
| `phase`, `stim_var`, `mi_type` | | Slice keys |
| `n_bouts`, `H_stim`, `H_syll`, `mi_raw`, `mi_mm` | | Same semantics as pooled, trial-local |
| `null_circ_mean`, `null_circ_p` | | Filled only with `--trial-nulls` (circular; uses `--n-perm`, default 1000); else empty / NaN |
| `excess` | bits | `mi_mm − null_circ_mean` when nulls on; else empty / NaN |

Optional eligibility gates (off by default): `--min-run-bouts`, `--min-h-stim`.

---

## 6. `mi_trial_animal_summaries.csv`

One row = trajectory summaries for one animal × `(phase, stim_var, mi_type)` from that animal’s trial rows.

| Column | Units | Description |
|--------|-------|-------------|
| `animal_id`, `sex`, `strain`, `tx` | | Strata |
| `phase`, `stim_var`, `mi_type` | | Slice keys |
| `n_trials` | count | Trials contributing |
| `mean_mi_mm`, `median_mi_mm` | bits | Across trials (trial MI is upward-biased vs pooled — prefer slopes/deltas for “when”) |
| `mean_n_bouts`, `mean_H_stim` | | Diagnostics |
| `slope_vs_trial_ord` | bits/trial | OLS (ordinary least squares) fit: `mi_mm ~ trial_ord` |
| `early_late_delta` | bits | Career: mean(first **k=3**) − mean(last **k=3**); needs N ≥ 6; **+ ⇒ stronger early** |
| `slope_vs_excess` | bits/trial | OLS (ordinary least squares) fit of excess ~ `trial_ord` (`--trial-nulls`) |
| `early_late_delta_excess` | bits | Career early−late on excess (`--trial-nulls`) |
| `null_clear_fraction` | [0,1] | Fraction of trials with `null_circ_p < 0.05` (`--trial-nulls`) |
| `early_late_delta_within_session` | bits | Mean of per-session early−late (k=3, N_sess ≥ 6) |
| `early_late_delta_within_session_excess` | bits | Excess twin (`--trial-nulls`) |
| `n_sessions_used` | count | Sessions that contributed a within-session delta |

---

## 7. `group_mi_when_tests.csv`

Marginal group tests on **when-metrics**, **primary cells only** (`run` × occupancy × duty|dist).

| Column | Description |
|--------|-------------|
| `factor`, `level_a`, `level_b` | Same as §4 |
| `phase`, `stim_var`, `mi_type` | Primary cells |
| `metric` | Which summary column was tested (see below) |
| `n_a`, `n_b`, `median_a`, `median_b`, `stat`, `p`, `q_bh`, `test` | Test output |

**`metric` values**

| Without `--trial-nulls` | With `--trial-nulls` |
|-------------------------|----------------------|
| `slope_vs_trial_ord` | those + `slope_vs_excess` |
| `early_late_delta` | + `early_late_delta_excess` |
| *(within-session not in this table’s metric list by default — see summaries / sliced)* | |

**BH-FDR (`q_bh`)** — within families **B** (slope) and **C** (career early−late delta), matching §8. With `--trial-nulls`, primary endpoints are excess metrics; raw `mi_mm` trajectory metrics are exploratory (`q_bh` blank).

Row count this run: **12** (no nulls) or **24** (with nulls).

---

## 8. `group_mi_sliced_tests.csv` (`--sliced-tests`)

One-hold and two-hold **simple effects** on primary cells. Arm omitted if n < 5.

| Column | Description |
|--------|-------------|
| `fdr_family` | `A` / `B` / `C` / `D` (see below) |
| `hold_sex`, `hold_strain`, `hold_tx` | Held-fixed strata; **blank = not held** |
| `contrast_factor` | `sex`, `genotype`, or `tx` |
| `level_a`, `level_b` | Levels compared within the slice |
| `phase`, `stim_var`, `mi_type` | Primary cells |
| `metric` | Endpoint tested |
| `n_a`, `n_b`, `median_a`, `median_b`, `stat`, `p` | Test |
| `q_bh` | Benjamini–Hochberg (BH) FDR-adjusted q **within** `fdr_family`; blank for exploratory rows |
| `test` | Usually `mannwhitneyu` |

### FDR (false discovery rate) families

| Family | Endpoint in family (with `--trial-nulls`) | Without nulls |
|--------|-------------------------------------------|---------------|
| **A** | pooled `mi_mm` (from `mi_per_animal`) | same |
| **B** | `slope_vs_excess` | `slope_vs_trial_ord` |
| **C** | `early_late_delta_excess` (career) | `early_late_delta` |
| **D** | `early_late_delta_within_session_excess` | `early_late_delta_within_session` |

When `--trial-nulls` is on, **raw** slope/delta metrics are still emitted with `p` but **`q_bh` empty** (exploratory; ~43% of rows in the nulls run).

**Hold depth**

- **One-hold:** exactly one of `hold_*` filled (e.g. genotype contrast with `hold_sex=M`).
- **Two-hold:** two filled (e.g. genotype with `hold_sex=M` and `hold_tx=RBSF-1`).

This run: **192** rows without nulls, **336** with nulls.

---

## 9. Summary JSON sidecars

### `join_stimulus_bouts_summary.json`

Join coverage: input/output row counts, trials seen/joined/skipped, experiment filter, paths, confound note.

### `compute_stimulus_mi_summary.json`

Compute coverage: `n_animals`, `n_mi_rows`, `n_group_tests`, `n_iti_control_flags`, `iti_flagged[]`, paths, `per_trial`, `trial_nulls`, `n_trial_mi_rows`, `n_trial_animal_summaries`, `n_when_group_tests`, `n_sliced_group_tests`, confound note.

---

## Reading order (recommended)

1. `stimulus_bin_edges.json` — codebook  
2. `mi_per_animal.csv` + `group_mi_tests.csv` + `group_mi_excess_tests.csv` — is coupling present? marginal strata?  
3. Quarantine `iti_control_flag` / iti×dist  
4. `mi_trial_animal_summaries.csv` + `group_mi_when_tests.csv` — does coupling **change** over career?  
5. `group_mi_sliced_tests.csv` — conditional simple effects; prefer `q_bh` within family over raw `p`  
6. `mi_per_trial.csv` — only for trajectory plots / QC (quality control)  

---

## Related plans

- [stimulus_syllable_mi](../.cursor/plans/stimulus_syllable_mi_a29cf8bb.plan.md) — original pooled pilot  
- [stimulus_mi_when_coupling](../.cursor/plans/stimulus_mi_when_coupling.plan.md) — trial / ordinal  
- [stimulus_mi_sliced_factorial](../.cursor/plans/stimulus_mi_sliced_factorial.plan.md) — slices + within-session  
- [ADR-0006](adr/0006-stimulus-mi-trial-trajectory-not-mixed.md) (architecture decision record)
