---
title: Litmus Ladder
type: ops
assay: nor-impress
status: na
claim_kind: na
verdict: na
tags:
  - claim/ops
  - assay/nor-impress
---
# Litmus Ladder (theory-indexed)

Gates on Prox/Quad (and cousins) are named by **theory home**, not A/B/C letters. **Family A** (BH family letter on `F *-A`) is a different alphabet — leave it alone.

| Old letter | Role | Theory / hypothesis home | Canonical name |
|---|---|---|---|
| Litmus A | Assay preference in `noSD` (Wilcoxon vs 0 / paired nvl−fam) | [[T1 Recognition NOR]] · [[H Assay Validity NOR]] | **litmus T1-assay** |
| Litmus B | Condition Kruskal (within-sex BH family) | [[T1 Recognition NOR]] · [[H Recognition Separators]] (Prox/Quad) | **litmus T1** |
| Litmus C | Session paired Δ (Wilcoxon Δ; Δ×condition) | Protocol dynamics — **not** [[T2 Physio Coupling]] | **litmus sessΔ** |

**Not T0:** [[T0 Altered Behavior]] is the *bonus condition* board (engagement Δ, companions). T1-assay is a prerequisite under T1, not a T0 claim. A plain condition test on a non-recognition metric would be **litmus T0** — that letter was never the Prox/Quad A gate.

**Cascade:** T1-assay → T1 → sessΔ. Grammar stays sealed until T1-assay is decided (and T1 nulls do not unlock grammar fishing).

Artifact tokens still on disk may say `litmus_a` / `litmus_a_pass`; runners dual-write the theory-indexed names — see [[Concordance]].
