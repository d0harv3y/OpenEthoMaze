---
title: E NGramSeq Bigram Richness
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
# E NGramSeq Bigram Richness

**Status:** lava — clean null, do not reuse without a new contract. #lava
**Scalar:** `bigram_richness` = #distinct bigrams in the M = 108 resampled-pair draw (raw counts).
**Grain:** animal × NOR_TX × nvl_obj, portable cluster alphabet.
**Family:** [[F NGramSeq-A]] (with [[E NGramSeq Pair MI]]).

## Vocab spine

- FORMULAS § TRANSITION → bigram-richness row (added 2026-10-02).
- STATS §§ Descriptive vs inferential, Uncorrected vs multiplicity-corrected, Rank vs mean.
- INTERPRET: occupancy-vs-transition clause.

## Estimates

| Campaign | Result | Run |
|---|---|---|
| Ladder pooled, cluster (locked) | 0/4 family (F p≈0.385, M p≈0.672); medians F ≈ 33, M ≈ 28, flat | [[Run NGramSeq]] |
| Ladder expanded / full grid | 0/24 · 0/48 FDR | [[Run NGramSeq Expanded]] · [[Run NGramSeq Full Grid]] |
| Ladder raw ×21 + recog ×9 + per-animal ×9 (exploratory) | 0/192 combined; richness never hits uncorrected anywhere | [[V NGramSeq Null]] |

## Verdict

Null. [[V NGramSeq Null]] · [[E NGramSeq Pair MI]] · [[F NGramSeq-A]]
