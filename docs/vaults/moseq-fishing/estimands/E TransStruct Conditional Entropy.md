---
title: E TransStruct Conditional Entropy
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
# E TransStruct Conditional Entropy

**Status:** lava — clean null, do not reuse without a new contract. #lava
**Scalar:** `H_next_given_curr` = H(next | current) in bits under animal P with empirical current-state weights.
**Grain:** animal × NOR_TX × nvl_obj (same bout stream as [[E TransStruct TV Distance]]).
**Family:** [[F TransStruct-A]] (with [[E TransStruct TV Distance]]).

## Vocab spine

- FORMULAS § TRANSITION → "Conditional entropy of next bout" (row added 2026-10-01 for this gap).
- FORMULAS § TEST → "k-group rank (independent groups)"; STATS §§ Descriptive vs inferential, Uncorrected vs multiplicity-corrected, Rank vs mean.
- INTERPRET: occupancy-vs-transition clause.
- CONTEXT nouns; PROTOCOL-STRATA + BOSS-SESSION-MAP wire.

## Strata parameters

- NOR: `condition` noSD/GHSD/RBSD within sex.
- VAST/RAM/Alz: unestimated.

## Estimates

| Campaign | Alphabet | Result | Run |
|---|---|---|---|
| Ladder pooled, cluster (locked) | 21 portable cluster_id | 0/4 (best M p≈0.078 → q≈0.312) | [[Run Transition Structure]] |
| Ladder expanded / full grid | same | 0/24 · 0/48 FDR | [[Run Transition Structure Expanded]] · [[Run Transition Structure Full Grid]] |
| Ladder pooled, raw ×21 models | raw per model | **0/21 models** (count-robust: \|r\|≈0.1 with count) | [[V TransStruct Raw Exploratory]] |
| Recog pooled ×9 (cluster + raw) | both | 1/36 uncorrected (cluster), 0/36 (raw); downsampled 0/36 | [[V TransStruct Cross-Campaign]] |
| Per-animal ×9 cells | animal-local | H + H_norm **0/36, 0 uncorrected** (best p≈0.071) | [[V TransStruct Cross-Campaign]] |

## Verdict

Null in all 48 model-or-cell families under FDR. The count-clean metric never moves.

- [[V TransStruct Null]] · [[V TransStruct Cross-Campaign]] · [[F TransStruct-A]] · [[E TransStruct TV Distance]]
