---
title: V ProxComp Per-Scalar Null
type: verdict
assay: nor-impress
status: lava
claim_kind: alphabet-bound
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
  - alphabet-bound
---
# V ProxComp Per-Scalar Null

**Date:** 2026-10-08  
**Scope:** [[Run ProxComp Per-Scalar]] / [[F ProxComp Per-Scalar]] / [[F ProxComp Per-Scalar Score Contract]]  
**Claim kind:** composition `#alphabet-bound`.  
**Gate:** Kruskal on each of `dr_shannon_prox` / `dr_richness_prox` / `dr_hill2_prox` by `condition` within sex at `NOR_TX` × `nvl_obj`; BH **within each scalar** (m=2).

## Verdict

**Fail on condition** for all three scalar families (0/2 FDR each).  
**Pass** Litmus T1-assay (sex=all): shannon, richness, hill2, and time DR cousins all Wilcoxon-hit with median > 0.

Splitting the joint ProxComp-A bag into per-scalar families **did not** create condition hits — p's remain large (best uncorrected ≈0.32 on M hill2).

## Evidence

| Family | Cell | p | q_bh |
|--------|------|---|------|
| ProxComp-Shannon | F | 0.576 | 0.576 |
| ProxComp-Shannon | M | 0.420 | 0.576 |
| ProxComp-Richness | F | 0.365 | 0.548 |
| ProxComp-Richness | M | 0.548 | 0.548 |
| ProxComp-Hill2 | F | 0.732 | 0.732 |
| ProxComp-Hill2 | M | 0.318 | 0.636 |

Assay litmus (sex=all): shannon med≈0.083 p≈4e-4; richness med≈0.176 p≈1e-6; hill2 med≈0.099 p≈0.012; time med≈0.52 p≈1.5e-8.

## Locked language

> Under one-BH-family-per-scalar ProxComp (shannon / richness / Hill q=2), novel-ball composition preference passes assay litmus in controls, but condition does not separate any scalar family at recognition (0 FDR hits in each m=2 bag).

## Exploratory: sex-stratified discovery control (2026-10-09)

**Not a reseal** of [[F ProxComp Per-Scalar Score Contract]] (sealed bag remains m=2 F+M per scalar). Deck/report exploration only — see [[Run DR Framed Deck Exemplar]] / [[Motion Sequencing DR Framed Report]].

Same Kruskal p’s; BH within `(sex, metric)` (m=1 → q=p) and sex-stratified joint composition (m=3/sex: shannon+richness+hill2).

| Alphabet | Best cell | p (= q if m=1) | FDR @ 0.05 |
|----------|-----------|----------------|------------|
| Sealed `cluster_id` | M `dr_hill2_prox` | 0.318 | 0 hits (any bag) |
| Exemplar raw | M `dr_hill2_prox` | 0.112 | 0 hits (any bag) |

Joint m=6 (all scalars × sex) or sex-strat joint m=3 only **inflates** q. **No condition FDR hit survives** sex-stratification or joint composition bags.

## Related

- [[V ProxComp Null]] — joint m=4 seal (same qualitative null)
- [[F ProxComp Per-Scalar]] · [[F ProxComp Per-Scalar Score Contract]] · [[Run ProxComp Per-Scalar]]
- [[Run DR Framed Deck Exemplar]] · [[Motion Sequencing DR Framed Report]]
- [[H Investigation Quality]] · [[NOR IMPRESS Index]]
