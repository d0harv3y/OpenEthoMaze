---
title: F QuadComp-A
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
# F QuadComp-A

**Family spec** — [[F QuadComp-A Score Contract]] (declared **2026-10-06** before peeking).  
**Status:** lava — condition null; Litmus T1-assay passed. #lava  
**Parent:** [[H Investigation Quality]] / [[H Recognition Separators]].  
**Verdict:** [[V QuadComp Null]]  
**Run:** [[Run QuadComp]]

## Plain ask

At `NOR_TX` × `nvl_obj`, does `condition` separate signed quadrant composition contrasts (`dr_shannon_quad`, `dr_richness_quad`)?

## Design strip (summary)

| Axis | Lock |
|------|------|
| ROI | object-assigned arena quadrants + pooled `other` |
| Alphabet | `cluster_id` (pilot model) |
| Min frames | N = 10 both object quads |
| Primary metrics | `dr_shannon_quad`, `dr_richness_quad` |
| Association | Kruskal by `condition` within sex |
| Family size | 2 × F/M = **4** |
| Hit rule | `q_bh < 0.05` within QuadComp-A |

## Outcome

| Cell | p | q_bh |
|------|---|------|
| F `dr_shannon_quad` | 0.072 | 0.202 |
| M `dr_shannon_quad` | 0.155 | 0.202 |
| F `dr_richness_quad` | 0.202 | 0.202 |
| M `dr_richness_quad` | 0.117 | 0.202 |

**0/4** `hit_fdr05`. Litmus T1-assay (Wilcoxon vs 0, `noSD`, sex=all): **pass** both DR cousins.

### Constituents — Litmus T1-assay pass; [[F QuadLevel-A]] fail

| Token | Litmus T1-assay sex=all (`noSD`, paired nvl−fam) |
|-------|-------------------------------------------|
| `fam_shannon_quad` → `nvl_shannon_quad` | med 2.16 → 2.32; Δ p≈0.027 **hit** |
| `fam_richness_quad` → `nvl_richness_quad` | med 8 → 10; Δ p≈0.00019 **hit** |

[[F QuadLevel-A]] (8-cell BH, confirmatory after peek): **0/8** FDR; **0/8** uncorrected. Closest F `fam_richness_quad` p≈0.053.

## Artifacts

→ [[Run QuadComp]]

## Related

- [[F QuadComp-A Score Contract]] · [[F QuadLevel-A]] · [[F ProxComp-A Score Contract]] · [[F ProxGram-A Score Contract]]
- [[V QuadComp Null]]
