---
title: F QuadLevel-A
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
  - QuadLevel-A
---
# F QuadLevel-A

**Declared:** 2026-10-06 **after** peeking panel D / exploratory Kruskal (user-authorized confirmatory BH — not a blind lock).  
**Parent DR family:** [[F QuadComp-A]] (signed contrasts only).  
**Verdict home:** [[V QuadComp Null]]  
**Run:** [[Run QuadComp]] · `quad_level_tests_long.csv`

## Plain ask

At `NOR_TX` × `nvl_obj`, does `condition` separate **absolute** fam/nvl quadrant Shannon / richness levels (not the signed DR cousins)?

## Design strip

| Axis | Lock |
|------|------|
| Metrics | `fam_shannon_quad`, `nvl_shannon_quad`, `fam_richness_quad`, `nvl_richness_quad` |
| Association | Kruskal by `condition` within sex |
| Family size | 4 × F/M = **8** |
| Hit rule | `q_bh < 0.05` within QuadLevel-A only (separate from QuadComp-A / TimeQuad-A) |
| Eligibility | same N=10 exclusive both-object-quad gate as QuadComp contrasts |

## Outcome

**0/8** `hit_fdr05`; **0/8** uncorrected `hit_p05`. Closest: F `fam_richness_quad` p≈0.053 (q≈0.28); F `fam_shannon_quad` p≈0.070 (q≈0.28).

Assay paired nvl−fam in `noSD` (Litmus T1-assay companion, outside this BH) still hits sex=all — see [[V QuadComp Null]].

## Related

- [[F QuadComp-A]] · [[F ProxLevel-A]] · [[V QuadComp Null]]
