---
title: F ProxComp Per-Scalar
type: family
assay: nor-impress
status: lava
claim_kind: alphabet-bound
verdict: fail
tags:
  - claim/family
  - assay/nor-impress
  - lava
  - alphabet-bound
---
# F ProxComp Per-Scalar

**Family spec** — [[F ProxComp Per-Scalar Score Contract]] (declared **2026-10-08** before peeking).  
**Status:** lava — Litmus T1-assay pass (incl. hill2); condition fail in each scalar family. #lava  
**Parent:** [[H Investigation Quality]] / [[H Recognition Separators]].  
**Verdict:** [[V ProxComp Per-Scalar Null]]  
**Run:** [[Run ProxComp Per-Scalar]]

## Plain ask

At `NOR_TX` × `nvl_obj`, does `condition` separate each ProxComp DR cousin when BH is applied **one scalar at a time** (m=2: F, M)?

| Family | Metric | m | Outcome |
|--------|--------|---|---------|
| ProxComp-Shannon | `dr_shannon_prox` | 2 | 0/2 FDR |
| ProxComp-Richness | `dr_richness_prox` | 2 | 0/2 FDR |
| ProxComp-Hill2 | `dr_hill2_prox` | 2 | 0/2 FDR |

Does **not** replace sealed joint [[F ProxComp-A]] (m=4).

## Related

- [[F ProxComp Per-Scalar Score Contract]] · [[V ProxComp Per-Scalar Null]] · [[Run ProxComp Per-Scalar]]
- [[F ProxComp-A]] · [[V ProxComp Null]]
- [[Run Prox Quad Comp Figs]]
