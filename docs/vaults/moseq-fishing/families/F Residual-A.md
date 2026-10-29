---
title: F Residual-A
type: family
assay: nor-impress
status: lava
claim_kind: na
verdict: fail
tags:
  - claim/family
  - assay/nor-impress
  - lava
---
# F Residual-A

**Family spec** (locked **2026-10-05** before peeking; redundancy litmus).  
**Parent:** [[H Non-Recognition Condition Separators]] / [[T0 Altered Behavior]].  
**Status:** lava — clean null. #lava  
**Members:** [[E Residual Shannon]] · [[E Residual Cond Entropy]] · [[E Residual Pair MI]]  
**Verdict:** **fail** (0/6 FDR, 0/6 uncorrected). [[V Residual Litmus Null]]

## Plain ask

Within sex at `NOR_TX` × `nvl_obj`, after residualizing declared syllable scalars on speed / immobile / `frac_near`, does `condition` still separate the residuals?

## Design strip (complete experiment)

| Axis | Lock |
|------|------|
| Cohort | 144 animals; 0 incomplete drops |
| Grain | `animal × NOR_TX × nvl_obj` |
| Y (raw) | `shannon_bits` (slides_pack consensus); `H_next_given_curr` (TransStruct-A table); `pair_MI` (NGramSeq-A, M=108) |
| X (Layer A) | `mean_speed_mps` (protocol_dr @ NOR_TX session); `frac_still` (slides_pack @ grain); `frac_near_nvl` (median across models @ NOR_TX) |
| Residualizer | OLS **within sex**: `Y ~ intercept + X`; `resid = Y − Ŷ` |
| Association | Kruskal on `resid_*` by `condition` within sex |
| Family size | 3 residuals × F/M = **6** |
| Hit rule | `q_bh < 0.05` within Residual-A |
| Out of family | Raw-Y Kruskal companion table (descriptive only); DR Spearman |

## Outcome

| Cell | p | q_bh |
|------|---|------|
| F `resid_shannon_bits` | 0.473 | 0.650 |
| M `resid_shannon_bits` | 0.971 | 0.971 |
| F `resid_H_next_given_curr` | 0.254 | 0.578 |
| M `resid_H_next_given_curr` | 0.542 | 0.650 |
| F `resid_pair_MI` | 0.118 | 0.578 |
| M `resid_pair_MI` | 0.289 | 0.578 |

**Collinearity demo (not Family A):** raw M Shannon uncorrected p≈0.041 → residual p≈0.971.

## Artifacts

→ [[Run Residual Litmus]] (campaign root + CSVs + INFO + runner)

## Related

- [[V Residual Litmus Null]]
- [[H Non-Recognition Condition Separators]] · [[Motion Sequencing Honest Report]]
- [[F TransStruct-A]] · [[F NGramSeq-A]]
