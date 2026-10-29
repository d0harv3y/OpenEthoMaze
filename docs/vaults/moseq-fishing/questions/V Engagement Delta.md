---
title: V Engagement Delta
type: verdict
assay: nor-impress
status: treasure
claim_kind: clock-portable
verdict: partial
tags:
  - claim/verdict
  - assay/nor-impress
  - treasure
  - clock-portable
aliases:
  - Q5 Honesty Pass
  - V Engagement Delta Treasure
---
# V Engagement Delta

**Date:** 2026-09-23  
**Scope:** [[Run Condition on Paired Delta]] (+ companions [[Run Session Paired]], [[Run Presence Steps]], [[Run Object Prox DR]]).  
**Gate:** Kruskal on within-animal Δ across `condition` within sex; prefer consensus-animal / cross-model agreement; FDR `hit_fdr05` / `q_bh < 0.05` as declared in INFO; recognition-relevant steps preferred over acclimation-only.  
**Claim kind:** #clock-portable — occupancy / engagement clocks; not MoSeq insight ([[Claim Kind]]).

## Verdict

**Partial pass — not DR, but engagement Δ.**

Condition arms **do** separate on how much **near-object occupancy rises when objects appear** at challenge (`NOR_TX`), in **males**, with **21/21 model agreement** and consensus-animal FDR. That is **not** novel preference (DR still null). Sell as: SD blunts object-appearance engagement, not recognition preference.

**Kill as primary:** portable syllable-id DA; PERMANOVA dominated by `no_obj` × `near_0p10`; claiming “memory impairment.”

## Locked claim language (use this)

> At `NOR_TX`, within males, Kruskal on consensus (median-across-21-models) paired Δ shows condition modulates `delta_frac_near` for `no_obj→id_obj` and `no_obj→nvl_obj` (both `hit_fdr05`, q≈0.013, n=72). Medians: noSD rises more (≈0.23 / 0.35) than GHSD/RBSD (≈0.08–0.17). The recognition step alone (`id_obj→nvl_obj`) does **not** separate arms (p≈0.40). Same pattern appears in per-model scalar agreement (21/21) and in `presence_steps` majority-rule stars. Object-prox **DR** by condition remains a miss.

## Primary evidence (keep)

| Artifact | Finding |
|----------|---------|
| `condition_consensus_animal_condition_tests_long.csv` | **2** FDR hits total (of 336 tested): both `delta_frac_near`, M, `NOR_TX`, `full_session`/`frame_share` |
| `condition_scalar_condition_agreement.csv` | Same two cells: **frac_hit = 1.0** (21/21) |
| `presence_scalar_condition_kruskal_mean_model_p.csv` | Replicates: `frac_near` NOR_TX M `no_obj→id_obj` / `no_obj→nvl_obj` majority; also `mean_dist_any_m` on span |

**Medians (consensus animal, M, NOR_TX, full_session, frame_share):**

| Step | median Δ noSD | GHSD | RBSD | FDR |
|------|---------------|------|------|-----|
| `no_obj→id_obj` | 0.234 | 0.166 | 0.079 | yes |
| `no_obj→nvl_obj` | 0.351 | 0.130 | 0.134 | yes |
| `id_obj→nvl_obj` | 0.083 | 0.025 | 0.024 | **no** (p≈0.40) |

## Secondary / exploratory (cite carefully)

Full honesty boards for this fishing (not only this secondary table):

- Clock-portable trial/session steps → [[V Protocol Step Clocks]]
- Alphabet DA / Shannon / BC / cluster → [[V Composition Step Fishing]]

| Block | Hit rate (`hit_fdr05`) | Read |
|-------|------------------------|------|
| Per-model scalar **condition** axis | 144/7056 ≈ 2.0% | Sparse; concentrates NOR_TX + `no_obj→id_obj`; metrics BC / Δfrac_near / Shannon / richness — model-scattered except the consensus engagement cells |
| Per-model scalar **session** axis | 185/7056 ≈ 2.6% | Condition modulates session Δs (esp. `condition→REC3hr`, `BL→REC11hr` on `nvl_obj`) — recovery/trajectory story, not DR |
| Consensus animal **session** axis | 4/336 ≈ 1.2% | BC @ `nvl_obj` `condition→REC3hr` (M); some Δfrac_near |
| Arm contrasts (Mann–Whitney) | ~2–4% | Many noSD vs RBSD/GHSD on BC / Shannon / Δfrac_near — post-hoc to omnibus; do not replace Kruskal |
| Shannon-only tables | ~1.6–2.1% | Companion UNCERTAINTY; not preference |
| DA condition / session | 0.6% / 0.4% | Some near-prox male consensus (up to 76% models at BL/REC3 `id→nvl`) but median alphabet hit frac ~4–5%; **ids not portable** (ADR-0005) |
| `session_paired` scalar condition Kruskal (majority) | 12 cells | Aligns: frac_near / Shannon / richness session Δs by condition |
| `session_paired` cluster condition | `hit_fdr05` 0 on animal-median table; 6 majority stars; 3 col-FDR | Thin; cluster 13 etc. are support cast only |
| Object-prox DR × condition | **0** DR hits | Still null ([[H Novelty Preference DR]]) |

## Demote / do not lead with

| Artifact | Why |
|----------|-----|
| PERMANOVA endpoint (56 FDR) | Dominated by **female `no_obj` × `near_0p10` × `NOR_TX`** with huge F — wrong trial for “recognition”; near-grain sparsity risk |
| Raw `raw_syllable_id` DA lists | Model-local; low per-alphabet density |
| Bout_count / near_0p10 forks of the same engagement claim | Use **full_session × frame_share** as primary grain for the locked sentence |
| Parametric twin folder | Demoted in [[Prune Map]] |

## What this is / is not

| Is | Is not |
|----|--------|
| Condition modulation of **engagement Δ** when objects appear | Discrimination ratio / novel preference |
| Challenge-day (`NOR_TX`) male-focused | Settled sex×condition interaction model (females mostly quieter here) |
| Replicated across kpMS models + presence_steps | Proof of hippocampal memory failure |
| Natural bridge to [[H Investigation Quality]] (how they approach objects) | Physio correlation ([[V DR Physio Null]] already killed DR×physio) |

## Keep / demote for slides

| Keep | Demote |
|------|--------|
| Consensus + agreement figs for M `NOR_TX` `delta_frac_near` object-appearance steps | Alphabet DA volcanoes as “the” condition effect |
| Presence_steps companion violins / Kruskal for same cells | PERMANOVA `no_obj` near heatmaps as primary |
| Optional: one session-axis BC recovery panel as exploratory | Arm-contrast clutter without omnibus |

## Next

1. **Primary hunt:** recognition lattice + next candidates both **fail** ([[V Recognition Lattice Null]], [[V Candidate Lattice Null]]). Next needs **new** compute (quadrant / bout grammar).  
2. **Slides (side claim):** figures on [[Run Condition on Paired Delta]] (`fig_q5_engagement_delta_nor_tx_m` / `_f`).  
3. Optional arm post-hoc on engagement cells only if still cited.  
4. **Only after a recognition-linked lock:** physio follow-up ([[H Physio Coupling]]).

## Figure

Males (locked; inverted △):

![[fig_q5_engagement_delta_nor_tx_m.svg]]

Females (companion; circles — all three steps FDR miss here):

![[fig_q5_engagement_delta_nor_tx_f.svg]]

Source: [[Run Condition on Paired Delta]] · vault `attachments/` (copies of campaign `figures/`).

## Related

- [[H Non-Recognition Condition Separators]] (home board)
- [[H Recognition Separators]] (not this claim)
- [[V Recognition Lattice Null]]
- [[V Candidate Lattice Null]]
- [[Run Condition on Paired Delta]]
- [[Run Presence Steps]]
- [[Run Session Paired]]
- [[H Novelty Preference DR]]
- [[V DR Physio Null]]
- [[Prune Map]]
- [[NOR IMPRESS Index]]
- [[T0 Altered Behavior]]

#treasure
