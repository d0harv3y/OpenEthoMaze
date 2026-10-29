---
title: Run Prox Quad Per Animal
type: run
assay: nor-impress
status: ladder
claim_kind: alphabet-bound
verdict: exploratory
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - alphabet-bound
---
# Run Prox Quad Per Animal

**Status:** computed 2026-10-07; figures + Hill q=2 companion 2026-10-08 — animal-local Prox/Quad composition DR cousins; consensus Quad F `dr_shannon_quad` / `dr_hill2_quad` FDR hits (exploratory). #ladder  
**Parent:** [[Run Per Animal Paramscan]] · [[H Alphabet Equating]]  
**Verdict:** [[V Prox Quad Per Animal Exploratory]]  
**Comparable pooled pack:** [[Run Prox Quad Comp Figs]]

## Intent

Score object-stratified Shannon / richness / Hill q=2 DR (Quad + Prox) on each of 9 animal-local alphabets; compare to locked `cluster_id` and cohort raw×21 median. Figure packs: consensus + per-cell heatmaps (level) and session-step Δ (PHASE_STEPS).

## Links

- Hypothesis: [[H Alphabet Equating]] · [[H Investigation Quality]]
- Verdict: [[V Prox Quad Per Animal Exploratory]]
- Locked cousins: [[V QuadComp Null]] · [[V ProxComp Null]] · [[V Prox Quad Per Model Null]]
- Claim kind: #alphabet-bound (animal-local raw ids incommensurate; scalars compared)

## Artifacts

**Campaign root (scores):** `sack/datas/impress/nor_per_animal_paramscan/_nor_object_mi/simpler_first_prox_quad_per_animal/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `per_animal_per_cell.csv` | animal × session × cell — Shannon / richness / `hill2_eff` levels + DR |
| `per_cell_tests_long.csv` | Kruskal BH within cell (Family A m=4 stays shannon+richness) |
| `per_cell_litmus_a.csv` | Wilcoxon vs 0 in noSD |
| `consensus_per_animal.csv` | median across 9 cells @ TX |
| `consensus_tests_long.csv` | consensus Kruskal |
| `compare_spearman_across_alphabets.csv` | ρ vs cluster / cohort raw |
| `run_summary.json` | knobs |

**Runner (scores):** `scratch/nor_object_mi/simpler_first_prox_quad_per_animal.py`

### Figures — level (consensus + per-cell)

**Root:** `…/simpler_first_prox_quad_per_animal_figs/`

| Stem pattern | Role | Claim kind |
|--------------|------|------------|
| `figures/fig_consensus_{quad,prox}_{shannon,richness,hill2}_violins.*` | fam / nvl / DR × session; condition×sex | #alphabet-bound |
| `figures/fig_consensus_{quad,prox}_{shannon,richness,hill2}_kruskal_heatmap.*` | −log₁₀(p) BH family | #alphabet-bound |
| `figures/fig_per_model_{quad,prox}_{shannon,richness,hill2}_kruskal_heatmap.*` | y = paramscan cell | #alphabet-bound |
| `kruskal_consensus_*.csv` / `long_consensus_*.csv` | long tables for figures | D/I exploratory |

**Runner:** `scratch/nor_object_mi/fig_prox_quad_per_animal_comp_violins.py`

### Figures — session-step

**Root:** `…/simpler_first_prox_quad_per_animal_session_step_figs/`

| Stem pattern | Role | Claim kind |
|--------------|------|------------|
| `figures/fig_consensus_{quad,prox}_{shannon,richness,hill2}_session_step_violins.*` | Δ × PHASE_STEPS; fam/nvl share y-lims, DR own | #alphabet-bound |
| `figures/fig_consensus_*_session_step_kruskal_heatmap.*` | Kruskal on Δ ~ condition | #alphabet-bound |
| `figures/fig_per_model_*_session_step_kruskal_heatmap.*` | per-cell heatmaps | #alphabet-bound |

**Runner:** `scratch/nor_object_mi/fig_prox_quad_session_step_comp_violins.py --campaign per_animal`

**n thinning (session-step):** REC sessions are cohort subsets; `contrast_eligible` (N=10) required at both endpoints; pair intersection shrinks n below the 144/72/36 headline board.

## Related

- [[Run Prox Quad Comp Figs]] · [[Run Prox Quad Session Step Figs]] · [[Run Prox Quad Session Delta]]
- [[Claim Kind]] · [[Artifact Linking]]
