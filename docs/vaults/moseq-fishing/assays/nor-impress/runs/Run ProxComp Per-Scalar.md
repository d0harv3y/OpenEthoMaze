---
title: Run ProxComp Per-Scalar
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
# Run ProxComp Per-Scalar

**Status:** computed 2026-10-08 — Litmus T1-assay **pass** (shannon / richness / hill2 / time); per-scalar condition families **fail** (0/2 FDR each). #ladder  
**Contract:** [[F ProxComp Per-Scalar Score Contract]] · [[F ProxComp Per-Scalar]]  
**Verdict:** [[V ProxComp Per-Scalar Null]]  
**Sibling:** [[Run ProxComp]] (joint ProxComp-A seal)

## Artifacts

**Campaign root:** `sack/.../_nor_object_mi/simpler_first_prox_comp_per_scalar_fams/`

| File | Role |
|------|------|
| `prox_comp_per_animal.csv` | panel + DR cousins incl. hill2 + `dr_time_prox` |
| `prox_comp_litmus_t1_assay.csv` | assay Wilcoxon (3 composition + time) |
| `prox_comp_tests_long.csv` | ProxComp-Shannon / Richness / Hill2 (BH per metric) |
| `time_prox_tests_long.csv` | TimeProx-A |
| `INFO_prox_comp_per_scalar.md` | dictionary |

**Runner:** `scratch/nor_object_mi/simpler_first_prox_comp.py --per-scalar-families`

## Related

- [[Run ProxComp]] · [[Run Prox Quad Comp Figs]]
- [[V ProxComp Per-Scalar Null]] · [[F ProxComp Per-Scalar]]
- [[NOR IMPRESS Index]]
