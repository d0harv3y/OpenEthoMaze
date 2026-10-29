---
title: F ProxComp Per-Scalar Score Contract
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
  - ProxComp per-scalar score contract
---
# F ProxComp Per-Scalar Score Contract

**Declared:** 2026-10-08 (before peeking at this run's q).  
**Status:** executed — lava on condition; assay litmus T1-assay pass ([[V ProxComp Per-Scalar Null]] / [[Run ProxComp Per-Scalar]]). #lava  
**Parents:** [[H Investigation Quality]] · [[H Recognition Separators]] · [[H Assay Validity NOR]].  
**Executed family note:** [[F ProxComp Per-Scalar]]  
**Does not replace:** sealed joint [[F ProxComp-A]] / [[F ProxComp-A Score Contract]] (m=4 shannon+richness).

> [!note] Multiplicity design
> One BH family **per DR cousin** (m=2: F, M). Same ProxComp design strip as the joint contract; different FDR bags. See [[Joint vs Per-Grain FDR]].
>
> **Deck exploration (not a reseal):** sex-stratified per-scalar BH (m=1 within sex×metric) and sex-strat violin boards on [[Run DR Framed Deck Exemplar]] — still 0 condition FDR hits; see [[V ProxComp Per-Scalar Null]] § exploratory.

## Plain ask

On recognition trials (`trial=nvl_obj`), exclusive 0.10 m fam/nvl masks:

1. **Assay (T1-assay):** do `dr_shannon_prox` / `dr_richness_prox` / `dr_hill2_prox` show novel preference in `noSD`?
2. **Condition (T1):** does `condition` separate each scalar under its own BH family?

## Design strip

Same as [[F ProxComp-A Score Contract]] (r=0.10 m exclusive, N=10, `cluster_id` primary), plus Hill q=2 DR cousin in the primary condition menu (not companion-only).

| Family | Metric | Cells | Hit rule |
|--------|--------|-------|----------|
| ProxComp-Shannon | `dr_shannon_prox` | F, M | `q_bh < 0.05` within family |
| ProxComp-Richness | `dr_richness_prox` | F, M | same |
| ProxComp-Hill2 | `dr_hill2_prox` | F, M | same |

## Run

```powershell
uv run python scratch/nor_object_mi/simpler_first_prox_comp.py --per-scalar-families
```

Arts: `simpler_first_prox_comp_per_scalar_fams/` · [[Run ProxComp Per-Scalar]]

## Related

- [[F ProxComp Per-Scalar]] · [[V ProxComp Per-Scalar Null]] · [[Run ProxComp Per-Scalar]]
- [[F ProxComp-A Score Contract]] · [[V ProxComp Null]]
- [[Run Prox Quad Comp Figs]]
