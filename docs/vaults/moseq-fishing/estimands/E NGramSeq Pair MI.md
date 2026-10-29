---
title: E NGramSeq Pair MI
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
# E NGramSeq Pair MI

**Status:** lava — clean null, do not reuse without a new contract. #lava
**Scalar:** `pair_MI` = I(X1;X2) in bits over M = 108 resampled consecutive-bout pairs (Laplace α=1.0 on the K×K joint, K = 21).
**Grain:** animal × NOR_TX × nvl_obj, portable cluster alphabet.
**Family:** [[F NGramSeq-A]] (with [[E NGramSeq Bigram Richness]]).

## Vocab spine

- FORMULAS § TRANSITION → pair-MI row (added 2026-10-02).
- STATS §§ Descriptive vs inferential, Uncorrected vs multiplicity-corrected, Rank vs mean.
- INTERPRET: occupancy-vs-transition clause.

## Estimates

| Campaign | Result | Run |
|---|---|---|
| Ladder pooled, cluster (locked A) | 0/4 family | [[Run NGramSeq]] |
| Ladder expanded grains (NGramSeq-B) | **0/24 FDR** ([[V NGramSeq Expanded Null]]) | [[Run NGramSeq Expanded]] |
| Ladder full level grid (NGramSeq-C) | **0/48 FDR** ([[V NGramSeq Full Grid Null]]) | [[Run NGramSeq Full Grid]] |
| Ladder raw ×21 / Recog / Per-animal (exploratory) | 0 FDR — see [[V NGramSeq Null]] | (exploratory cousins on V) |

## Related

- [[F NGramSeq-A]] · [[F NGramSeq-B]] · [[F NGramSeq-C]]
- [[V NGramSeq Null]] · [[V NGramSeq Expanded Null]] · [[V NGramSeq Full Grid Null]]
- [[E NGramSeq Bigram Richness]]
