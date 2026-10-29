---
title: F Composition-Companion-B
type: family
assay: nor-impress
status: open
claim_kind: na
verdict: na
tags:
  - claim/family
  - assay/nor-impress
  - open
---
# F Composition-Companion-B

**Family spec** (locked **2026-10-05**; Shannon **level** at recovery acclimation).  
**Parent:** [[H Non-Recognition Condition Separators]] / [[T0 Altered Behavior]].  
**Status:** partial — **1/2** FDR (M only).  
**Verdict:** [[V Composition Companion Partial]]  
**Audit:** [[Run Composition Companion Audit]] · Shannon source `slides_pack/shannon/shannon_level_kruskal.csv`.

## Plain ask

At early recovery acclimation (`NOR_REC3hr` × `no_obj`), does `condition` separate consensus Shannon UNCERTAINTY levels within sex?

## Design strip (complete experiment)

| Axis        | Lock                                                            |
| ----------- | --------------------------------------------------------------- |
| Cohort      | `moseq_251017` REC3hr animals (n=36 per sex in consensus table) |
| Metric      | Shannon bits (consensus median-across-models animal level)      |
| Grain       | `animal × NOR_REC3hr × no_obj` (**level**, not Δ)               |
| Association | Kruskal by `condition` within sex                               |
| Family size | 2 (F, M)                                                        |
| Hit rule    | `q_bh < 0.05` within this 2-cell family                         |

**Not in family:** Shannon at `NOR_TX` / `nvl_obj`; richness; BC; trial-step Shannon.

## Cells + outcomes

| session | trial | sex | n | p | q_bh | median H noSD / GHSD / RBSD |
|---------|-------|-----|---|-----|------|-----------------------------|
| `NOR_REC3hr` | `no_obj` | F | 36 | 0.083 | 0.083 | 4.26 / 4.65 / 4.55 — **miss** |
| `NOR_REC3hr` | `no_obj` | M | 36 | 0.0020 | **0.0040** | 4.37 / 4.46 / 4.01 — **hit** |

## Honest read

Recovery-day acclimation UNCERTAINTY differs by arm in males (RBSD lower median H) — protocol / state, not recognition at challenge.

## Artifacts

→ [[Run Composition Companion Audit]] (Companion-B CSV + Shannon upstream)

## Related

- [[F Composition-Companion-A]] · [[F Stillness-Companion-A]] (clock twin) · [[H Non-Recognition Condition Separators]]
- [[V Composition Companion Partial]] · [[Motion Sequencing Honest Report]]
