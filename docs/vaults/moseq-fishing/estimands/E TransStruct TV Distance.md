---
title: E TransStruct TV Distance
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
# E TransStruct TV Distance

**Status:** lava — do not reuse as a condition separator without a new contract. #lava
**Scalar:** `trans_dist_to_nosd_ref` = total-variation distance (½·L1 over flattened P) between an animal's row-stochastic P(next | current) and the sex-pooled noSD reference P at the same grain.
**Grain:** animal × NOR_TX × nvl_obj (consecutive RLE bouts; raw diagonal counts are zero by construction).
**Family:** [[F TransStruct-A]] (with [[E TransStruct Conditional Entropy]]).

## Vocab spine

- FORMULAS § TRANSITION → "TV distance to reference law" (row added 2026-10-01 for this gap).
- FORMULAS § TEST → "k-group rank (independent groups)"; STATS §§ Descriptive vs inferential, Uncorrected vs multiplicity-corrected, Rank vs mean.
- INTERPRET: occupancy-vs-transition clause (transition ≠ composition).
- CONTEXT nouns; PROTOCOL-STRATA + BOSS-SESSION-MAP wire.

## Strata parameters

- NOR: `condition` noSD/GHSD/RBSD within sex; reference = sex-pooled noSD (in-sample bias noted).
- VAST/RAM/Alz: unestimated (no T1 claim posed there).

## Estimates

| Campaign | Alphabet | Result | Run |
|---|---|---|---|
| Ladder pooled, cluster (locked) | 21 portable cluster_id | 0/4 FDR, 0/4 uncorrected (F p≈0.334, M p≈0.168) | [[Run Transition Structure]] |
| Ladder expanded grains (TransStruct-B) | same | 0/24 FDR | [[Run Transition Structure Expanded]] |
| Ladder full level grid (TransStruct-C) | same | 0/48 FDR | [[Run Transition Structure Full Grid]] |
| Ladder pooled, raw ×21 models | raw per model | 12 within-model hits (six s2-1e5) → 0/84 global BH; TV–count r≈−0.9 → **snake** | [[V TransStruct Raw Exploratory]] |
| Recog pooled, cluster ×9 | campaign cluster map | 3/36 within-model → 0/36 global; same confound | [[V TransStruct Cross-Campaign]] |
| Recog pooled, raw ×9 | raw per model | 11/36 within-model (8/36 descriptive global) → downsampled rerun **0/36** | [[V TransStruct Cross-Campaign]] |
| Per-animal ×9 cells | animal-local | **undefined by design** (incommensurable alphabets) | [[V TransStruct Cross-Campaign]] |

## Verdict

Confounded where it hits, null where it's clean. The fixed-budget rerun kills all hits: TV moves with bout count, not transition structure.

- [[V TransStruct Null]] · [[V TransStruct Raw Exploratory]] · [[V TransStruct Cross-Campaign]]
- [[F TransStruct-A]] · [[E TransStruct Conditional Entropy]]
