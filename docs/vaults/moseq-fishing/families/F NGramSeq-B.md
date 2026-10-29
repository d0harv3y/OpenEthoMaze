---
title: F NGramSeq-B
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
# F NGramSeq-B

**Family spec** (locked **2026-10-05** before peeking; expanded grain panel).  
**Parent:** [[H Non-Recognition Condition Separators]] / [[T0 Altered Behavior]].  
**Status:** lava — clean null on FDR. #lava  
**Verdict:** [[V NGramSeq Expanded Null]]  
**Distinct from:** [[F NGramSeq-A]] (`NOR_TX` × `nvl_obj` only — do not merge BH families).  
**Parallel to:** [[F TransStruct-B]] (same six grains).  
**Multiplicity posture:** **joint panel** (m=24). Commensurate per-grain bar: [[F NGramSeq-PerGrain]] / [[Joint vs Per-Grain FDR]].

## Plain ask

Does `condition` separate fixed-budget pair MI / bigram richness at **expanded** grains?

## Design strip (complete experiment)

| Axis | Lock |
|------|------|
| Cohort / model / alphabet | Same as NGramSeq-A (pilot cluster_id, K=21) |
| Metrics | `pair_MI`, `bigram_richness` |
| Budget | **Per grain:** M = min transitions among animals in that grain (floor 50); seed base 7 + grain index |
| Reference | None (fixed budget) |
| Association | Kruskal by `condition` within sex |
| Family size | 2 × 6 grains × 2 sex = **24** |
| Hit rule | `q_bh < 0.05` within NGramSeq-B |

### Grains + budgets (this run)

| session       | trial          | n   | M   |
| ------------- | -------------- | --- | --- |
| `NOR_TX`      | `full_session` | 144 | 450 |
| `NOR_TX`      | `no_obj`       | 144 | 129 |
| `NOR_TX`      | `id_obj`       | 144 | 89  |
| `NOR_BL`      | `nvl_obj`      | 144 | 87  |
| `NOR_REC3hr`  | `nvl_obj`      | 72  | 119 |
| `NOR_REC11hr` | `nvl_obj`      | 72  | 64  |

**Not in B:** `NOR_TX` × `nvl_obj` (Family A).

## Outcome

**0/24 `hit_fdr05`.** Two uncorrected `hit_p05` only (q ≫ 0.05 after BH) — see [[V NGramSeq Expanded Null]].

## Artifacts

→ [[Run NGramSeq Expanded]] (campaign root + CSVs + runner)

## Related

- [[H Non-Recognition Condition Separators]] · [[F NGramSeq-A]] · [[F NGramSeq-C]] · [[F NGramSeq-PerGrain]] · [[F TransStruct-B]]
- [[V NGramSeq Null]] · [[V NGramSeq Expanded Null]] · [[Joint vs Per-Grain FDR]]
