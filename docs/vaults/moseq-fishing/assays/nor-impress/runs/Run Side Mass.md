---
title: Run Side Mass
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
# Run Side Mass

**Status:** computed 2026-09-23 — Family SideMass-A **fail** ([[V Side Geometry Null]]). #ladder  
**Parent:** [[H Recognition Separators]]

## Intent

Per-animal nvl-side geometry (recognition-linked spatial I); 16 Kruskal cells.

## Links

- Estimand: [[E Side Geometry]]
- Verdict: [[V Side Geometry Null]]
- Hypothesis: [[H Recognition Separators]]

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_side_mass/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `side_mass_per_animal.csv` | D — per-animal geometry scalars |
| `side_mass_tests_long.csv` | I — SideMass-A (0 FDR; best q≈0.107) |
| `INFO_side_mass.md` | Data dictionary |
| `run_summary.json` | Knobs + pass/fail |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_side_mass.py`  
**Litmus:** `test_side_mass.py`

## Related

- [[Run Syllable Spatial Heatmaps]] — D-only pools (precedent)
- [[Run Object Prox DR]] — different scalar (prox preference)
- [[V Candidate Lattice Null]]
