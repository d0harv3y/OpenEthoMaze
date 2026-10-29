---
title: Run Transition Structure Expanded
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
# Run Transition Structure Expanded

**Status:** computed — Family [[F TransStruct-B]] **fail** ([[V TransStruct Expanded Null]]). #ladder  
**Parent:** [[H Non-Recognition Condition Separators]]

## Intent

Same scalars as TransStruct-A at six expanded grains (incl. `NOR_TX` × `full_session` concat); 24-cell BH. Excludes A grain (`NOR_TX` × `nvl_obj`).

## Links

- Family: [[F TransStruct-B]]
- Estimands: [[E TransStruct TV Distance]] · [[E TransStruct Conditional Entropy]] (same scalars, expanded grain)
- Verdict: [[V TransStruct Expanded Null]]
- Sibling: [[Run Transition Structure Full Grid]] (all 12 levels)

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_transition_structure_expanded/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `transition_structure_expanded_per_animal.csv` | D — animal × grain |
| `transition_structure_expanded_tests_long.csv` | I — 24 cells; 0 FDR |
| `run_summary.json` | `pass_family_b: false` |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_transition_structure_expanded.py`
