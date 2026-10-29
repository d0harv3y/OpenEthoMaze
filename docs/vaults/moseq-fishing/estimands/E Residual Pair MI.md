---
title: E Residual Pair MI
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
# E Residual Pair MI

**Status:** lava — clean null under [[F Residual-A]] / [[V Residual Litmus Null]]. #lava
**Scalar:** `resid_pair_MI` = OLS residual of fixed-budget pair mutual information after `Y ~ mean_speed_mps + frac_still + frac_near_nvl` within sex at `NOR_TX` × `nvl_obj`.
**Raw `Y` source:** [[Run NGramSeq]] → `ngram_seq_per_animal.csv` column `pair_MI`.
**Grain:** animal × NOR_TX × nvl_obj.
**Family:** [[F Residual-A]].

## Estimates

| Campaign | Result |
|---|---|
| Ladder `moseq_251017` | F p≈0.118 / M p≈0.289 — **null** (Residual-A; best residual cell) |

## Related

- [[F Residual-A]] · [[E NGramSeq Pair MI]] · [[V Residual Litmus Null]] · [[Run Residual Litmus]]
- Raw Y path owned by [[Run NGramSeq]]
