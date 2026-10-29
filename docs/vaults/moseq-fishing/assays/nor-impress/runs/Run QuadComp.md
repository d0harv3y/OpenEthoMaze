---
title: Run QuadComp
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
# Run QuadComp

**Status:** computed 2026-10-06 — Litmus T1-assay **pass** (comp + `dr_time_quad`); QuadComp-A / TimeQuad-A / [[F QuadLevel-A]] **fail** ([[V QuadComp Null]]). #ladder  
**Parent:** [[H Investigation Quality]] / [[H Recognition Separators]]  
**Contract:** [[F QuadComp-A Score Contract]] · [[F ProxComp-A Score Contract]]

## Intent

Object-assigned arena quadrants (`fam_quad` / `nvl_quad` / `other`) → syllable richness / Shannon DR cousins + clock-portable `dr_time_quad` on `nvl_obj`; `cluster_id` alphabet. Level family = absolute fam/nvl scalars.

## Links

- Family: [[F QuadComp-A]] · [[F QuadLevel-A]]
- Verdict: [[V QuadComp Null]] · [[V ProxComp Null]]
- Sibling circular gate: [[Run ProxComp]]
- Session Δ: [[Run Prox Quad Session Delta]]

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_quad_comp/`

| File | Role |
|------|------|
| `quad_comp_per_animal.csv` | D — panel + DR cousins + `dr_time_quad` + constituents (`fam_shannon_quad`, `nvl_shannon_quad`, `fam_richness_quad`, `nvl_richness_quad`) |
| `quad_comp_eligibility.csv` | D — N=10 drop rates |
| `quad_comp_litmus_t1_assay.csv` (legacy alias `quad_comp_litmus_a.csv`) | I — assay Wilcoxon (comp + time) |
| `quad_comp_tests_long.csv` | I — QuadComp-A (0 FDR) |
| `time_quad_tests_long.csv` | I — TimeQuad-A (0 FDR) |
| `quad_level_tests_long.csv` | I — QuadLevel-A (0 FDR; confirmatory) |
| `INFO_quad_comp.md` | Data dictionary |
| `run_summary.json` | Knobs + pass/fail |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_quad_comp.py`  
**Litmus:** `test_quad_comp.py`

## Related

- [[Run Side Mass]] — occupancy geometry null (different estimand)
- [[Run Object Prox DR]] — classic time DR
- [[Run Syllable Spatial Heatmaps]] — diagonal placement precedent
- [[V Prox Quad SessDelta Null]] — Litmus sessΔ
