---
title: F TransStruct-PerGrain
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
# F TransStruct-PerGrain

**Family spec** (locked **2026-10-05**; commensurate with [[F TransStruct-A]]).  
**Parent:** [[H Non-Recognition Condition Separators]] / [[T0 Altered Behavior]].  
**Status:** lava — clean null under per-grain BH. #lava #alphabet-bound  
**Verdict:** [[V TransStruct PerGrain Null]]  
**Multiplicity posture:** **per-grain** (not joint) — see [[Joint vs Per-Grain FDR]].

## Plain ask

At **each** NOR level grain separately, does `condition` separate bout-transition scalars under the **same** BH bar as TransStruct-A (m=4)?

## Design strip (complete experiment)

| Axis | Lock |
|------|------|
| Grains | **12** level grains = {`NOR_BL`,`NOR_TX`,`NOR_REC3hr`,`NOR_REC11hr`} × {`no_obj`,`id_obj`,`nvl_obj`} |
| Excluded from primary | Synthetic `full_session` (optional B-panel companion only) |
| Metrics | `trans_dist_to_nosd_ref`, `H_next_given_curr` |
| Alphabet / model | Same as A/B/C (portable `cluster_id`, pilot paramscan, Laplace α=1.0, min 20 bouts) |
| Association | Kruskal by `condition` within sex (same p as TransStruct-C tables) |
| **Family size** | **m = 4 per grain** (2 metrics × F/M) — **commensurate with A** |
| Hit rule (within grain) | `hit_fdr05` ⇔ `q_bh < 0.05` **within that grain only** |
| Grain pass | ≥1 `hit_fdr05` in that grain’s 4-cell family |
| Global sentence | Descriptive only: count of grains that pass — **no second-level BH** in this contract |
| Scalars | **Not recomputed** — BH re-applied on existing Kruskal `p` |

### Honesty (peek / joint history)

Raw `p` were previously visible under joint [[F TransStruct-C]] (m=48) and [[F TransStruct-B]] (m=24). This contract changes **multiplicity only**. It does **not** invent a softer joint panel by shrinking m after the fact without naming the new posture.

### Relation to A / B / C

| Family | Posture | m |
|--------|---------|---|
| [[F TransStruct-A]] | Per-grain (1 grain) | 4 |
| [[F TransStruct-B]] / [[F TransStruct-C]] | **Joint** panel | 24 / 48 |
| **This** | Per-grain (12 grains) | 4 each |

A’s grain (`NOR_TX` × `nvl_obj`) is included; under per-grain BH it remains a miss (same 4 cells as A).

## Outcome

**0/12 grains pass.** **0** cell-level `hit_fdr05` under per-grain m=4. Seven uncorrected `hit_p05` only (best per-grain q ≈ 0.050 on F `H_next_given_curr` @ `NOR_REC11hr` × `no_obj` — still miss under `q < 0.05`).

Optional B-panel companion (`full_session` + five other B grains): **0/6** grains pass; 2 uncorrected only.

## Artifacts

→ [[Run Sequence PerGrain BH]]  
Primary tables: `simpler_first_sequence_per_grain_bh/transstruct_full_grid_per_grain_*.csv`

## Related

- [[Joint vs Per-Grain FDR]] · [[F TransStruct-A]] · [[F TransStruct-C]] · [[F NGramSeq-PerGrain]]
- [[H Non-Recognition Condition Separators]] · [[Motion Sequencing Honest Report]]
