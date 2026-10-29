---
title: F NGramSeq-PerGrain
type: family
assay: nor-impress
status: lava
claim_kind: alphabet-bound
verdict: na
tags:
  - claim/family
  - assay/nor-impress
  - lava
  - alphabet-bound
---
# F NGramSeq-PerGrain

**Family spec** (locked **2026-10-05**; commensurate with [[F NGramSeq-A]]).  
**Parent:** [[H Non-Recognition Condition Separators]] / [[T0 Altered Behavior]].  
**Status:** lava — clean null under per-grain BH. #lava #alphabet-bound  
**Verdict:** [[V NGramSeq PerGrain Null]]  
**Multiplicity posture:** **per-grain** (not joint) — see [[Joint vs Per-Grain FDR]].  
**Parallel to:** [[F TransStruct-PerGrain]].

## Plain ask

At **each** NOR level grain separately, does `condition` separate fixed-budget pair MI / bigram richness under the **same** BH bar as NGramSeq-A (m=4)?

## Design strip (complete experiment)

| Axis | Lock |
|------|------|
| Grains | Same **12** level grains as [[F TransStruct-PerGrain]] / [[F TransStruct-C]] |
| Metrics | `pair_MI`, `bigram_richness` |
| Budget | Unchanged from NGramSeq-C (per-grain M already locked there) |
| Association | Kruskal by `condition` within sex (same p as NGramSeq-C tables) |
| **Family size** | **m = 4 per grain** — **commensurate with A** |
| Hit rule (within grain) | `q_bh < 0.05` within that grain only |
| Grain pass | ≥1 `hit_fdr05` in the grain’s 4-cell family |
| Global sentence | Descriptive grain-pass count only — **no second-level BH** |
| Scalars | **Not recomputed** — BH re-applied on existing Kruskal `p` |

### Honesty (peek / joint history)

Same as TransStruct-PerGrain: `p` previously visible under joint [[F NGramSeq-C]] / [[F NGramSeq-B]]. New multiplicity posture only.

## Outcome

**0/12 grains pass.** **0** cell-level `hit_fdr05`. Three uncorrected `hit_p05` only (best per-grain q ≈ 0.100).

Optional B-panel companion: **0/6** grains pass; 2 uncorrected only.

## Artifacts

→ [[Run Sequence PerGrain BH]]  
Primary tables: `simpler_first_sequence_per_grain_bh/ngramseq_full_grid_per_grain_*.csv`

## Related

- [[Joint vs Per-Grain FDR]] · [[F NGramSeq-A]] · [[F NGramSeq-C]] · [[F TransStruct-PerGrain]]
- [[H Non-Recognition Condition Separators]] · [[V NGramSeq PerGrain Null]]
