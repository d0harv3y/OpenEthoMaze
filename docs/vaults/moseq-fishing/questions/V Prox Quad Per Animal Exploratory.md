---
title: V Prox Quad Per Animal Exploratory
type: verdict
assay: nor-impress
status: rabbit-hole
claim_kind: alphabet-bound
verdict: exploratory
tags:
  - claim/verdict
  - assay/nor-impress
  - rabbit-hole
  - alphabet-bound
---
# V Prox Quad Per Animal Exploratory

**Date:** 2026-10-07 (scores); figures + Hill q=2 2026-10-08  
**Scope:** [[Run Prox Quad Per Animal]] on `nor_per_animal_paramscan` (144 × 9).  
**Not a lock** — does not overturn [[V QuadComp Null]] / [[V ProxComp Null]] (`cluster_id`).

## Verdict

| Layer                                | Result                                                                                       |
| ------------------------------------ | -------------------------------------------------------------------------------------------- |
| Litmus A (sex=all, DR cousins)       | **pass** — hit rate 1.0 across cells                                                         |
| Within-cell Family A (9 × Quad/Prox) | Quad: **4/9** cells FDR (all F `dr_shannon_quad`); Prox: **2/9** (F `dr_shannon_prox`)       |
| Consensus median ×9 cells            | Quad F `dr_shannon_quad` **hit_fdr05** (p≈0.00086, q≈0.003); Prox F same metric q≈0.066 miss |
| Hill q=2 companion (not Family A)    | Quad F `dr_hill2_quad` **hit_fdr05** @ NOR_TX (q≈0.021); same direction pattern as Shannon   |
| Males                                | null on consensus                                                                            |

Direction (F consensus medians @ NOR_TX, exploratory):

| Metric | noSD | GHSD | RBSD |
|--------|------|------|------|
| `dr_shannon_quad` | +0.037 | +0.061 | −0.016 |
| `dr_hill2_quad` | +0.040 | +0.082 | −0.046 |

Composition DR rank **GHSD > noSD > RBSD** on this animal-local board — **not** classic time-DR (pooled locked boards often put noSD on top at TX). Do not sell as recognition separator.

## Compare to other alphabets (Spearman @ TX)

| Metric | per-animal median vs cluster | vs cohort raw median | cohort raw vs cluster |
|--------|------------------------------|----------------------|------------------------|
| `dr_shannon_quad` | ρ≈0.35 | ρ≈0.48 | ρ≈0.66 |
| `dr_richness_quad` | ρ≈0.70 | ρ≈0.69 | ρ≈0.79 |
| `dr_shannon_prox` | ρ≈0.29 | ρ≈0.37 | ρ≈0.73 |
| `dr_richness_prox` | ρ≈0.59 | ρ≈0.68 | ρ≈0.70 |

Animal-local Shannon DR tracks portable cluster only weakly; richness DR agrees more. Cohort raw×21 stays closer to cluster than per-animal fits do.

## Composition vs recognition (read)

- **Levels** (`fam_*` / `nvl_*` Shannon / richness / `hill2_eff`): repertoire width / evenness near each object — investigation-quality-ish D.
- **DR cousins** (`dr_*`): signed preference-of-**repertoire**, not preference-of-**time**. Assay litmus can pass while condition Kruskal fails on locked alphabets.
- **Hill q=2** (`hill2_eff` = 1/∑p²): effective-number companion; **not** sealed Family A (still shannon + richness only on contracts).

## n ≠ 72 / 36

Headline sex×condition cells are thinned by (1) REC session cohort subsets, (2) `contrast_eligible` min-frames N=10 on both masks, (3) session-step pair intersection. See figure footnotes / long CSVs on [[Run Prox Quad Per Animal]].

## Figures

Comparable pooled 2×2: [[Run Prox Quad Comp Figs]]. Per-animal violins + heatmaps (level + session-step): [[Run Prox Quad Per Animal]] § Figures.

## Interpretation (exploratory)

Within-animal fam/nvl DR is alphabet-legal without remapping. Cross-animal Kruskal still mixes unequal alphabet sizes — treat consensus F hits as **leads**, not sealed Family A. Locked recognition separators remain the `cluster_id` nulls unless the lab promotes this board.

## Related

- [[Run Prox Quad Per Animal]] · [[Run Prox Quad Comp Figs]] · [[Run Prox Quad Session Step Figs]]
- [[H Alphabet Equating]] · [[H Investigation Quality]]
- [[V QuadComp Null]] · [[V ProxComp Null]] · [[V Prox Quad Per Model Null]]
