---
title: E Residual Cond Entropy
type: estimand
assay: nor-impress
status: lava
claim_kind: na
verdict: na
tags:
  - claim/estimand
  - assay/nor-impress
  - lava
---
# E Residual Cond Entropy

**Status:** lava — clean null under [[F Residual-A]] / [[V Residual Litmus Null]]. #lava
**Scalar:** `resid_H_next_given_curr` = OLS residual of bout conditional entropy after `Y ~ mean_speed_mps + frac_still + frac_near_nvl` within sex at `NOR_TX` × `nvl_obj`.
**Raw `Y` source:** [[Run Transition Structure]] → `transition_structure_per_animal.csv` column `H_next_given_curr`.
**Grain:** animal × NOR_TX × nvl_obj.
**Family:** [[F Residual-A]].

## Estimates

| Campaign | Result |
|---|---|
| Ladder `moseq_251017` | F p≈0.254 / M p≈0.542 — **null** (Residual-A) |

## Related

- [[F Residual-A]] · [[E TransStruct Conditional Entropy]] · [[V Residual Litmus Null]] · [[Run Residual Litmus]]
- Raw Y path owned by [[Run Transition Structure]]
