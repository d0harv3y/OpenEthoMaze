---
title: E Residual Shannon
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
# E Residual Shannon

**Status:** lava — clean null under [[F Residual-A]] / [[V Residual Litmus Null]]. #lava
**Scalar:** `resid_shannon_bits` = OLS residual of consensus Shannon bits after `Y ~ mean_speed_mps + frac_still + frac_near_nvl` within sex at `NOR_TX` × `nvl_obj`.
**Raw `Y` source:** [[Run Slides Pack]] → `shannon/shannon_animal_level.csv` column `p` (median-across-models Shannon at animal × session × trial).
**Grain:** animal × NOR_TX × nvl_obj.
**Family:** [[F Residual-A]].

## Estimates

| Campaign | Result |
|---|---|
| Ladder `moseq_251017` | F p≈0.473 / M p≈0.971 — **null** (Residual-A) |

## Related

- [[F Residual-A]] · [[V Residual Litmus Null]] · [[Run Residual Litmus]]
- [[E Residual Cond Entropy]] · [[E Residual Pair MI]]
