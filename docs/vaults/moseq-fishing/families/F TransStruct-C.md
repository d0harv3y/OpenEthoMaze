---
title: F TransStruct-C
type: family
assay: nor-impress
status: lava
claim_kind: na
verdict: na
tags:
  - claim/family
  - assay/nor-impress
  - lava
---
# F TransStruct-C

**Family spec** (locked **2026-10-05** before peeking; **complete NOR level grid**).  
**Parent:** [[H Non-Recognition Condition Separators]] / [[T0 Altered Behavior]].  
**Status:** lava — clean null on FDR. #lava  
**Verdict:** [[V TransStruct Full Grid Null]]  
**Distinct from:** [[F TransStruct-A]] / [[F TransStruct-B]] (do not merge BH).  
**Multiplicity posture:** **joint panel** (m=48) — “anywhere on the 12-grain board?” For per-grain m=4 (commensurate with A), see [[F TransStruct-PerGrain]] / [[Joint vs Per-Grain FDR]].

## Plain ask

Across **all** `session × trial` level grains of the NOR ladder, does `condition` separate bout-transition scalars?

## Design strip (complete experiment)

| Axis | Lock |
|------|------|
| Grains | **12** = {`NOR_BL`,`NOR_TX`,`NOR_REC3hr`,`NOR_REC11hr`} × {`no_obj`,`id_obj`,`nvl_obj`} |
| Excluded | Synthetic `full_session` concat (B only) |
| Metrics | `trans_dist_to_nosd_ref`, `H_next_given_curr` |
| Alphabet / model | Portable `cluster_id`, pilot `paramscan_s1-1e8_s2-1e5_ss-50`, Laplace α=1.0, min 20 bouts |
| Association | Kruskal by `condition` within sex |
| Family size | 2 × 12 × 2 = **48** |
| Hit rule | `q_bh < 0.05` within TransStruct-C |
| n | 144 at BL/TX; 72 at REC3/REC11 |

## Outcome

**0/48 `hit_fdr05`.** Seven uncorrected `hit_p05` only (all q ≫ 0.05 after 48-cell BH) — see verdict note.

## Artifacts

→ [[Run Transition Structure Full Grid]] (campaign root + CSVs + runner)

## Related

- [[F NGramSeq-C]] · [[F TransStruct-B]] · [[F TransStruct-PerGrain]] · [[H Non-Recognition Condition Separators]] · [[V TransStruct Full Grid Null]]
- [[Joint vs Per-Grain FDR]]
