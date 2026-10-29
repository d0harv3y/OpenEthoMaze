---
title: Run Prox Quad Session Delta
type: run
assay: nor-impress
status: ladder
claim_kind: na
verdict: fail
tags:
  - claim/run
  - assay/nor-impress
  - ladder
---
# Run Prox Quad Session Delta

**Status:** computed 2026-10-06 — Litmus sessΔ: Wilcoxon dynamics **hit**; Δ×condition **0 FDR** ([[V Prox Quad SessDelta Null]]). #ladder  
**Parents:** [[Run QuadComp]] · [[Run ProxComp]]  
**Exploratory figure packs (incl. Hill q=2, per-animal):** [[Run Prox Quad Session Step Figs]]

## Intent

Within-animal session-step Δ on `nvl_obj` for Quad/Prox DR cousins, time twins, and `fam_*`/`nvl_*` shannon–richness levels. Primary story step: **BL→TX**. Sealed I board — shannon/richness/time only; Hill q=2 lives on the figure packs, not this BH.

## Design strip

| Axis | Lock |
|------|------|
| Steps | `PHASE_STEPS` (BL→TX, TX→REC*, BL→REC*, …) |
| Metrics | 7 Quad + 7 Prox (DR shannon/richness, `dr_time_*`, 4 levels) |
| Eligibility | same N=10 gates as parent boards (`contrast_eligible` / `time_contrast_eligible` at both sessions) |
| Dynamics I | Wilcoxon Δ vs 0 (sex=all + F/M; uncorrected) |
| Condition I | Kruskal on Δ by `condition` within sex; BH within board × step (Quad-SessDelta / Prox-SessDelta) |

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_prox_quad_session_delta/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `quad_session_delta_per_animal.csv` | D — paired Δ rows |
| `prox_session_delta_per_animal.csv` | D — paired Δ rows |
| `session_delta_wilcoxon_long.csv` | I — Δ vs 0 |
| `session_delta_kruskal_long.csv` | I — Δ×condition (0 FDR) |
| `INFO_prox_quad_session_delta.md` | dictionary |
| `run_summary.json` | knobs |

**Runner:** `scratch/nor_object_mi/simpler_first_prox_quad_session_delta.py`

## Related

- [[V Prox Quad SessDelta Null]] · [[V QuadComp Null]] · [[V ProxComp Null]]
- [[Run Prox Quad Session Step Figs]] · [[Run Prox Quad Comp Figs]]
- [[V Occupancy Delta Null]]
- [[H Investigation Quality]] · [[H Recognition Separators]]
- [[F ProxComp-A Score Contract]] § C
