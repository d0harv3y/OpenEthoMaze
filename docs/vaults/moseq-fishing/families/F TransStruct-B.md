---
title: F TransStruct-B
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
# F TransStruct-B

**Family spec** (locked **2026-10-05** before peeking; expanded grain panel).  
**Parent:** [[H Non-Recognition Condition Separators]] / [[T0 Altered Behavior]].  
**Status:** lava — clean null on FDR. #lava  
**Verdict:** [[V TransStruct Expanded Null]]  
**Distinct from:** [[F TransStruct-A]] (`NOR_TX` × `nvl_obj` only — do not merge BH families).  
**Multiplicity posture:** **joint panel** (m=24) — harder list-keeping than A. For the commensurate bar at each grain, see [[F TransStruct-PerGrain]] / [[Joint vs Per-Grain FDR]]. Do **not** read B as “A repeated at six grains with the same q bar.”

## Plain ask

Does `condition` separate bout-transition scalars at **expanded** grains (challenge full session, other trials, baseline / recovery `nvl_obj`)?

## Design strip (complete experiment)

| Axis | Lock |
|------|------|
| Cohort | `moseq_251017` ladder; pilot kpMS `paramscan_s1-1e8_s2-1e5_ss-50` |
| Alphabet | Portable HDBSCAN `cluster_id` (21 states) via `syllable_prototypes_clustered.csv` |
| Unit | Consecutive **bouts** (RLE); Laplace α=1.0; min 20 bouts |
| Metrics | `trans_dist_to_nosd_ref` (TV = ½ L1 to sex-pooled noSD P at same grain); `H_next_given_curr` (bits) |
| Association | Kruskal by `condition` within sex |
| Family size | 2 × 6 grains × 2 sex = **24** |
| Hit rule | `q_bh < 0.05` within TransStruct-B |

### Grains (locked)

| session | trial | n animals | Notes |
|---------|-------|-----------|-------|
| `NOR_TX` | `full_session` | 144 | Concat bouts `no_obj→id_obj→nvl_obj`; inter-trial boundary = one transition |
| `NOR_TX` | `no_obj` | 144 | Acclimation |
| `NOR_TX` | `id_obj` | 144 | Familiarization |
| `NOR_BL` | `nvl_obj` | 144 | Baseline recognition |
| `NOR_REC3hr` | `nvl_obj` | 72 | Early recovery |
| `NOR_REC11hr` | `nvl_obj` | 72 | Late recovery |

**Not in B:** `NOR_TX` × `nvl_obj` (Family A).

## Outcome

**0/24 `hit_fdr05`.** Uncorrected-only (both q≈0.35 after BH):

| Cell | p | q_bh |
|------|---|------|
| M `trans_dist_to_nosd_ref` · `NOR_REC3hr` × `nvl_obj` | 0.037 | 0.352 |
| M `H_next_given_curr` · `NOR_TX` × `id_obj` | 0.046 | 0.352 |

## Artifacts

→ [[Run Transition Structure Expanded]] (campaign root + CSVs + runner)

## Related

- [[H Non-Recognition Condition Separators]] · [[V TransStruct Expanded Null]]
- [[F TransStruct-A]] · [[F TransStruct-C]] · [[F TransStruct-PerGrain]] · [[F NGramSeq-B]] · [[V TransStruct Null]]
- [[Joint vs Per-Grain FDR]]
