---
title: F Composition-Companion-A
type: family
assay: nor-impress
status: open
claim_kind: na
verdict: pass
tags:
  - claim/family
  - assay/nor-impress
  - open
---
# F Composition-Companion-A

**Family spec** (locked **2026-10-05**; session-step companions — **not** a T1 recognition lock).  
**Parent:** [[H Non-Recognition Condition Separators]] / [[T0 Altered Behavior]].  
**Status:** **pass** (4/4 `hit_fdr05` under re-declared BH).  
**Verdict:** [[V Composition Companion Partial]]  
**Audit:** [[Run Composition Companion Audit]] (reads consensus CSVs; no recompute of compositions).

## Plain ask

At declared **session-step** grains, does `condition` modulate composition DIFFERENCE (Bray–Curtis) or engagement-shaped session Δ (`delta_frac_near`)?

## Design strip (complete experiment)

| Axis | Lock |
|------|------|
| Cohort | IMPRESS NOR ladder `moseq_251017` (144 animals; REC arms n=72 where applicable) |
| Association | Independent groups — Kruskal–Wallis on `condition` ∈ {noSD, GHSD, RBSD} within sex |
| Grain type | **Session-step** (paired within-animal Δ across sessions, then Kruskal on Δ by condition) |
| Composition source | Consensus animal medians across 21 kpMS models (`condition_consensus_animal_session_tests_long.csv`) |
| Alphabet | Portable cluster / frame-share or bout-count weighting as locked per cell — **not** raw `raw_syllable_id` headlines |
| Hit rule | `hit_fdr05` ⇔ `q_bh < 0.05` within this **4-cell** family only |

**Not in family:** trial-step novelty (`id→nvl`); level PERMANOVA; TransStruct / NGramSeq; engagement Δ at `NOR_TX` object-appearance (separate treasure).

## Cells (4) + outcomes

| grain | sex | metric | trial | session_step | weighting | n | p | q_bh | median Δ noSD / GHSD / RBSD |
|-------|-----|--------|-------|--------------|-----------|---|-----|------|------------------------------|
| `near_0p10` | M | `braycurtis` | `nvl_obj` | `condition→REC3hr` | `bout_count` | 35 | 0.0010 | **0.0035** | 0.370 / 0.327 / 0.487 |
| `near_0p10` | M | `braycurtis` | `nvl_obj` | `condition→REC3hr` | `frame_share` | 35 | 0.0018 | **0.0035** | 0.435 / 0.441 / 0.647 |
| `full_session` | M | `delta_frac_near` | `id_obj` | `BL→condition` | `frame_share` | 72 | 0.012 | **0.012** | 0.086 / 0.014 / −0.052 |
| `full_session` | F | `delta_frac_near` | `no_obj` | `BL→REC11hr` | `frame_share` | 36 | 0.0050 | **0.0066** | 0.035 / 0.144 / 0.056 |

All four `hit_fdr05`.

## Honest read

- BC near-object **turnover** challenge → early recovery on **`nvl_obj`** (M) — trajectory / composition DIFFERENCE, not contemporaneous preference at `NOR_TX`.
- `delta_frac_near` session steps — engagement-shaped cousins of [[V Engagement Delta]]; not novelty-step recognition.

## Artifacts

→ [[Run Composition Companion Audit]] (audit CSVs + upstream consensus paths)

## Related

- [[H Non-Recognition Condition Separators]]
- [[F Composition-Companion-B]] · [[V Composition Companion Partial]]
- [[V Recognition Lattice Null]] (BC REC3 footnote) · [[V Engagement Delta]]
- [[Motion Sequencing Honest Report]]
