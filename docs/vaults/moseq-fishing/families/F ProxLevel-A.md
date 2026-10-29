---
title: F ProxLevel-A
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
aliases:
  - ProxLevel-A
---
# F ProxLevel-A

**Declared:** 2026-10-06 **after** peeking panel D / exploratory Kruskal (user-authorized confirmatory BH — not a blind lock).  
**Parent DR family:** [[F ProxComp-A]] (signed contrasts only).  
**Verdict home:** [[V ProxComp Null]]  
**Run:** [[Run ProxComp]] · `prox_level_tests_long.csv`

## Plain ask

At `NOR_TX` × `nvl_obj`, does `condition` separate **absolute** fam/nvl exclusive-prox Shannon / richness levels?

## Design strip

| Axis | Lock |
|------|------|
| Metrics | `fam_shannon_prox`, `nvl_shannon_prox`, `fam_richness_prox`, `nvl_richness_prox` |
| Association | Kruskal by `condition` within sex |
| Family size | 4 × F/M = **8** |
| Hit rule | `q_bh < 0.05` within ProxLevel-A only |
| Eligibility | N=10 both exclusive 0.10 m masks |

## Outcome

**0/8** `hit_fdr05`; **0/8** uncorrected `hit_p05`. Best raw cells ≈ M `fam_richness_prox` p≈0.16 / M `fam_shannon_prox` p≈0.19 (q≈0.72).

Litmus T1-assay paired nvl−fam in `noSD` remains strong (both sexes) — assay preference, not condition separation.

## Related

- [[F ProxComp-A]] · [[F QuadLevel-A]] · [[V ProxComp Null]]
