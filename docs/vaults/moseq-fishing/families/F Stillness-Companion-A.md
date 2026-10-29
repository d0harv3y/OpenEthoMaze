---
title: F Stillness-Companion-A
type: family
assay: nor-impress
status: open
claim_kind: clock-portable
verdict: pass
tags:
  - claim/family
  - assay/nor-impress
  - open
  - clock-portable
---
# F Stillness-Companion-A

**Family spec** (locked **2026-10-06**; immobile fraction **level** at recovery acclimation).  
**Parent:** [[H Non-Recognition Condition Separators]] / [[T0 Altered Behavior]].  
**Status:** **pass** — **2/2** FDR.  
**Verdict:** [[V Protocol Step Clocks]]  
**Claim kind:** **#clock-portable** (threshold stillness — no syllable alphabet).  
**Audit:** [[Run Stillness Companion Audit]] · source `slides_pack/frac_still/frac_still_kruskal.csv`.

## Plain ask

At early recovery acclimation (`NOR_REC3hr` × `no_obj`), does `condition` separate immobile frame share (`frac_still`) within sex?

## Design strip (complete experiment)

| Axis        | Lock                                                            |
| ----------- | --------------------------------------------------------------- |
| Cohort      | `moseq_251017` REC3hr animals (n=36 per sex)                    |
| Metric      | `frac_still` (immobile frames / trial frames; slides_pack)      |
| Grain       | `animal × NOR_REC3hr × no_obj` (**level**, not Δ)               |
| Association | Kruskal by `condition` within sex                               |
| Family size | 2 (F, M)                                                        |
| Hit rule    | `q_bh < 0.05` within this **2-cell** family                     |

**Not in family:** `frac_still` at other sessions / trials; session-step stillness Δ; Shannon (alphabet twin → [[F Composition-Companion-B]]); engagement Δ at `NOR_TX`.

**Why re-declare:** The slides-pack 24-cell level BH already keeps both cells (`q≈0.048`). This family locks the **pre-declared** recovery-acclimation stillness ask (same grain as Shannon Companion-B) under a commensurate m=2 BH.

## Cells + outcomes

| session | trial | sex | n | p | q_bh (m=2) | median `frac_still` noSD / GHSD / RBSD |
|---------|-------|-----|---|-----|------------|----------------------------------------|
| `NOR_REC3hr` | `no_obj` | F | 36 | 0.0040 | **0.0040** | 0.464 / 0.360 / 0.457 — **hit** |
| `NOR_REC3hr` | `no_obj` | M | 36 | 0.0036 | **0.0040** | 0.457 / 0.405 / **0.617** — **hit** |

Both `hit_fdr05`.

## Honest read

Early-recovery empty-arena stillness differs by arm in **both** sexes. Pattern is sex-asymmetric (F: GHSD lowest still; M: RBSD highest still). Protocol / state companion — **not** recognition at challenge, **not** MoSeq insight. Clock twin of Shannon Companion-B (M-only UNCERTAINTY hit at the same grain).

## Artifacts

→ [[Run Stillness Companion Audit]] (`stillness_companion_a_tests.csv`) · upstream [[Run Slides Pack]] `frac_still/`

## Related

- [[V Protocol Step Clocks]] · [[F Composition-Companion-B]] (Shannon twin) · [[V Composition Companion Partial]]
- [[H Non-Recognition Condition Separators]] · [[V Engagement Delta]]
- [[Claim Kind]] · [[Motion Sequencing Honest Report]]
