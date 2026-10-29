---
title: Run Prox Quad Session Step Figs
type: run
assay: nor-impress
status: ladder
claim_kind: mixed
verdict: exploratory
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - mixed
---
# Run Prox Quad Session Step Figs

**Status:** computed 2026-10-08 — session-step (PHASE_STEPS) figure packs for pooled min0 + per-animal paramscan; includes Hill q=2. #ladder  
**I cousin (sealed sessΔ):** [[Run Prox Quad Session Delta]] / [[V Prox Quad SessDelta Null]] — dynamics hit, Δ×condition 0 FDR on locked metrics.  
**Parents:** [[Run QuadComp]] · [[Run ProxComp]] · [[Run Prox Quad Per Animal]]

## Intent

Within-animal paired Δ of fam / nvl / DR composition scalars across protocol session steps. Exploratory D/I figure boards — **not** a replacement for the sealed sessΔ BH families.

## Design strip

| Axis | Lock |
|------|------|
| Steps | `PHASE_STEPS` / `STEP_LAB` (BL→TX primary story) |
| Metrics | Shannon / richness / Hill q=2 × Quad + Prox |
| Eligibility | `contrast_eligible` at both endpoints |
| Plot y-lims | fam and nvl share per figure; DR axis separate |
| n | thinned by REC subset ∩ eligibility ∩ pair intersection |

## Artifacts

### Pooled (cohort raw×21 + cluster)

**Root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_prox_quad_session_step_figs_min0/`

| Stem pattern | Role |
|--------------|------|
| `figures/fig_consensus_{quad,prox}_{shannon,richness,hill2}_session_step_violins.*` | Δ violins |
| `figures/fig_*_session_step_kruskal_heatmap.*` | consensus / cluster / per-model |
| `*_session_step.csv` | long + Kruskal tables |

### Per-animal (9 cells)

**Root:** `sack/datas/impress/nor_per_animal_paramscan/_nor_object_mi/simpler_first_prox_quad_per_animal_session_step_figs/` — also linked from [[Run Prox Quad Per Animal]] § Figures.

**Runner:**

```text
uv run python scratch/nor_object_mi/fig_prox_quad_session_step_comp_violins.py --campaign cohort
uv run python scratch/nor_object_mi/fig_prox_quad_session_step_comp_violins.py --campaign per_animal
```

## Related

- [[V Prox Quad SessDelta Null]] · [[V Prox Quad Per Animal Exploratory]]
- [[Run Prox Quad Comp Figs]] · [[H Investigation Quality]]
