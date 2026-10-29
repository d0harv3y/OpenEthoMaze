---
title: Run Residual Litmus
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
# Run Residual Litmus

**Status:** computed — Family [[F Residual-A]] **fail** ([[V Residual Litmus Null]]). #ladder  
**Parent:** [[H Non-Recognition Condition Separators]]

## Intent

OLS-residualize Shannon / H(next\|current) / pair MI on speed + `frac_still` + `frac_near_nvl` at `NOR_TX` × `nvl_obj`; Kruskal residuals by `condition` within sex; BH over 6 cells.

## Links

- Family: [[F Residual-A]]
- Estimands: [[E Residual Shannon]] · [[E Residual Cond Entropy]] · [[E Residual Pair MI]]
- Verdict: [[V Residual Litmus Null]]
- Upstream Y: [[Run Transition Structure]] · [[Run NGramSeq]] · [[Run Slides Pack]]

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_residual_litmus/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `residual_litmus_per_animal.csv` | D — raw Y, X, resid_* |
| `residual_litmus_ols_coef.csv` | OLS coefs within sex |
| `residual_litmus_tests_long.csv` | I — Residual-A (6 cells; 0 FDR) |
| `residual_litmus_raw_companion_tests.csv` | Descriptive raw-Y Kruskal (not Family A) |
| `INFO_residual_litmus.md` | Data dictionary |
| `run_summary.json` | `pass_family_a: false` |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_residual_litmus.py`  
**Lib / litmus:** `residual_litmus.py`, `test_residual_litmus.py`

## Do not confuse with

- [[Run Transition Structure]] / [[Run NGramSeq]] — raw sequence separators
- [[V Engagement Delta]] — occupancy, not residualized syllables
