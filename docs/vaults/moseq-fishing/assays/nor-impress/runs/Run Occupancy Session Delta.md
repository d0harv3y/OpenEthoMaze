---
title: Run Occupancy Session Delta
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
# Run Occupancy Session Delta

**Status:** computed 2026-09-23 — Family OccSessDelta-A **fail** ([[V Occupancy Delta Null]]). #ladder  
**Parent:** [[H Recognition Separators]]

## Intent

Does `condition` modulate BL→TX object-prox occupancy Δ on `nvl_obj`? 4 Kruskal cells.

## Links

- Estimand: [[E Occupancy Session Delta]]
- Verdict: [[V Occupancy Delta Null]]
- Upstream occupancy: [[Run Object Prox DR]]

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_occupancy_session_delta/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `occupancy_session_delta_per_animal.csv` | D — BL→TX Δ scalars |
| `occupancy_session_delta_tests_long.csv` | I — OccSessDelta-A (0 FDR; best q≈0.135) |
| `INFO_occupancy_session_delta.md` | Data dictionary |
| `run_summary.json` | Knobs + pass/fail |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_occupancy_session_delta.py`

## Related

- [[Run Object Prox DR]] · [[Run Session Paired]]
- [[V Candidate Lattice Null]]
