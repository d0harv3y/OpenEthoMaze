---
title: Run Transition Structure Full Grid
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
# Run Transition Structure Full Grid

**Status:** computed — Family [[F TransStruct-C]] **fail** ([[V TransStruct Full Grid Null]]). #ladder  
**Parent:** [[H Non-Recognition Condition Separators]]

## Intent

Bout-transition TV + H(next\|current) at **all 12** NOR `session × trial` level grains; 48-cell BH. No synthetic `full_session`.

## Links

- Family: [[F TransStruct-C]]
- Estimands: [[E TransStruct TV Distance]] · [[E TransStruct Conditional Entropy]]
- Verdict: [[V TransStruct Full Grid Null]]
- Siblings: [[Run Transition Structure]] (A) · [[Run Transition Structure Expanded]] (B)

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_transition_structure_full_grid/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `transition_structure_full_grid_per_animal.csv` | D — animal × 12 grains |
| `transition_structure_full_grid_tests_long.csv` | I — 48 cells; 0 FDR |
| `run_summary.json` | `pass_family_c: false` |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_transition_structure_full_grid.py`
