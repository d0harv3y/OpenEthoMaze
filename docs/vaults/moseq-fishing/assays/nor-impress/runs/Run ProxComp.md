---
title: Run ProxComp
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
# Run ProxComp

**Status:** computed 2026-10-06 — Litmus T1-assay **pass** (comp + time); ProxComp-A / TimeProx-A / [[F ProxLevel-A]] **fail**. #ladder  
**Contract:** [[F ProxComp-A Score Contract]]  
**Sibling:** [[Run QuadComp]]

## Artifacts

**Campaign root:** `sack/.../_nor_object_mi/simpler_first_prox_comp/`

| File | Role |
|------|------|
| `prox_comp_per_animal.csv` | panel + DR cousins + `dr_time_prox` + constituents (`fam_shannon_prox`, `nvl_shannon_prox`, `fam_richness_prox`, `nvl_richness_prox`) |
| `prox_comp_litmus_t1_assay.csv` (legacy alias `prox_comp_litmus_a.csv`) | assay Wilcoxon |
| `prox_comp_tests_long.csv` | ProxComp-A 0/4 FDR |
| `time_prox_tests_long.csv` | TimeProx-A 0/2 FDR |
| `prox_level_tests_long.csv` | ProxLevel-A 0/8 FDR (confirmatory) |
| `INFO_prox_comp.md` | dictionary |

**Runner:** `scratch/nor_object_mi/simpler_first_prox_comp.py`

## Related

- [[V ProxComp Null]] · [[Run ProxComp Per-Scalar]] (per-scalar BH twin) · [[Run Prox Quad Session Delta]] · [[Run Object Prox DR]]
