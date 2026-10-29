---
title: Run Prox Quad Per Model
type: run
assay: nor-impress
status: ladder
claim_kind: alphabet-bound
verdict: fail
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - alphabet-bound
---
# Run Prox Quad Per Model

**Status:** exploratory 2026-10-06; Hill q=2 columns + figure packs 2026-10-08 — raw_syllable_id × 21 models; consensus **fail**; 1/21 lone Quad FDR (not promoted). #ladder  
**Parents:** [[Run QuadComp]] · [[Run ProxComp]]  
**Verdict:** [[V Prox Quad Per Model Null]] (cluster lock unchanged)  
**Figures:** [[Run Prox Quad Comp Figs]] · [[Run Prox Quad Session Step Figs]]

## Intent

Secondary alphabet board after portable `cluster_id`. BH within each model; consensus median then Kruskal. Emits Shannon / richness / `hill2_eff` levels + DR cousins (Family A stays shannon+richness).

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_prox_quad_per_model/` (min0 cousin: `…_per_model_min0/`)

| File | Role |
|------|------|
| `per_model_per_animal.csv` | animal × model × session — composition panel + DR |
| `INFO_prox_quad_per_model.md` | dictionary |

**Runner:** `scratch/nor_object_mi/simpler_first_prox_quad_per_model.py`

## Related

- [[V Prox Quad Per Model Null]] · [[V Prox Quad Per Animal Exploratory]]
- [[Claim Kind]] (#alphabet-bound; ADR-0005)
