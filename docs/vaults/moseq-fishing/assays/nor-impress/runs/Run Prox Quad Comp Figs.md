---
title: Run Prox Quad Comp Figs
type: run
assay: nor-impress
status: ladder
claim_kind: mixed
verdict: exploratory
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - mixed
---
# Run Prox Quad Comp Figs

**Status:** computed 2026-10-08 — pooled level figure pack (cluster + consensus raw×21 + per-model) including Hill q=2 companion and comparable NOR_TX DR panels. #ladder  
**Parents:** [[Run QuadComp]] · [[Run ProxComp]] · [[Run Prox Quad Per Model]]  
**Per-animal twin:** [[Run Prox Quad Per Animal]]

## Intent

Publication-style violins + Kruskal heatmaps for Prox/Quad composition levels and DR cousins on the locked ladder campaign (`moseq_251017`), with a side-by-side comparable 2×2 to the per-animal consensus layout.

## Links

- Locked I: [[V QuadComp Null]] · [[V ProxComp Null]] · [[V Prox Quad Per Model Null]]
- Exploratory lead: [[V Prox Quad Per Animal Exploratory]]
- Claim kind: cluster panels #alphabet-bound (portable `cluster_id`); raw×21 / per-model #alphabet-bound (ADR-0005)

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_prox_quad_comp_figs_min0/` ([[Campaign Roots]])

Score inputs (min0 cousins): `simpler_first_quad_comp_min0/`, `simpler_first_prox_comp_min0/`, `simpler_first_prox_quad_per_model_min0/`.

| File / stem | Role |
|-------------|------|
| `figures/fig_cluster_{quad,prox}_{shannon,richness,hill2}_violins.*` | portable alphabet levels + DR |
| `figures/fig_consensus_{quad,prox}_{shannon,richness,hill2}_violins.*` | median across 21 models |
| `figures/fig_*_kruskal_heatmap.*` | −log₁₀(p) BH families |
| `figures/fig_comparable_dr_violins_{cluster,consensus}_NOR_TX.*` | 2×2 matching per-animal layout |
| `kruskal_*.csv` / `long_*.csv` | long tables |

**Runners:**

```text
uv run python scratch/nor_object_mi/fig_prox_quad_comp_violins.py
uv run python scratch/nor_object_mi/fig_prox_quad_comparable_dr_panels.py
```

> [!note] Hill q=2
> `hill2_eff` / `dr_hill2_*` are exploratory companions. Sealed Family A remains shannon + richness only ([[F QuadComp-A Score Contract]] · [[F ProxComp-A Score Contract]]).

## Related

- [[Run Prox Quad Session Step Figs]] · [[Run Prox Quad Per Animal]]
- [[H Investigation Quality]] · [[Claim Kind]]
