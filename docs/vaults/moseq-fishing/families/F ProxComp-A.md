---
title: F ProxComp-A
type: family
assay: nor-impress
status: lava
claim_kind: na
verdict: fail
tags:
  - claim/family
  - assay/nor-impress
  - lava
---
# F ProxComp-A

**Family spec** — [[F ProxComp-A Score Contract]] (declared **2026-10-06** before peeking).  
**Status:** lava — Litmus T1-assay pass; condition fail. #lava  
**Parent:** [[H Investigation Quality]] / [[H Recognition Separators]].  
**Verdict:** [[V ProxComp Null]]  
**Run:** [[Run ProxComp]]

## Plain ask

At `NOR_TX` × `nvl_obj`, does `condition` separate signed prox-stratified composition contrasts (`dr_shannon_prox`, `dr_richness_prox`) after exclusive 0.10 m fam / nvl masks?

## Design strip (summary)

| Axis | Lock |
|------|------|
| Masks | exclusive r = 0.10 m fam vs nvl |
| Alphabet | `cluster_id` primary; per-model secondary ([[Run Prox Quad Per Model]]) |
| Min frames | **N = 10** both exclusive masks for finite contrasts |
| Primary metrics | `dr_shannon_prox`, `dr_richness_prox` |
| Association | Kruskal by `condition` within sex |
| Family size | 2 × F/M = **4** |
| Hit rule | `q_bh < 0.05` within ProxComp-A |
| Time twin | `dr_time_prox` → TimeProx-A (m=2; also fail) |

## Outcome

| Cell                          | Result                                |
| ----------------------------- | ------------------------------------- |
| Litmus T1-assay DR cousins (sex=all) | **pass** shannon + richness           |
| ProxComp-A                    | **0/4** `hit_fdr05`                   |
| TimeProx-A                    | **0/2** `hit_fdr05`                   |
| [[F ProxLevel-A]]             | **0/8** `hit_fdr05` (0/8 uncorrected) |

### Constituents — Litmus T1-assay pass; level Family A fail

| Token | Litmus T1-assay sex=all (`noSD`, paired nvl−fam) |
|-------|-------------------------------------------|
| `fam_shannon_prox` → `nvl_shannon_prox` | med 1.84 → 2.11; Δ p≈0.00056 **hit** |
| `fam_richness_prox` → `nvl_richness_prox` | med 6 → 10; Δ p≈9e-7 **hit** |
| Within sex | both sexes hit on shannon and richness Δ |

[[F ProxLevel-A]] Kruskal × condition: best p≈0.16 — see [[V ProxComp Null]].

## Artifacts

→ [[Run ProxComp]] · `simpler_first_prox_comp/`

## Related

- [[F ProxComp-A Score Contract]] · [[F ProxLevel-A]] · [[F ProxGram-A Score Contract]] · [[F QuadComp-A]]
- [[V ProxComp Null]] · [[Run Prox Quad Session Delta]] · [[Run Prox Quad Per Model]]
- [[H Investigation Quality]] · [[H Recognition Separators]]
