---
title: E Side Geometry
type: estimand
assay: nor-impress
status: open
claim_kind: na
verdict: fail
tags:
  - claim/estimand
  - assay/nor-impress
  - open
aliases:
  - Q5 SideMass Score Contract
---
# E Side Geometry

**Date:** 2026-09-23  
**Status:** declared → **computed** → [[V Side Geometry Null]] **fail** (0/16 `hit_fdr05`). Do not expand this family after peeking at `q`.  
**Parent:** [[H Recognition Separators]]  
**Run:** [[Run Side Mass]]

## One-line

Per-animal **nvl-side mass** after fam-left alignment — geometry share, **not** DR, **not** engagement Δ, **not** kpMS syllable ids.

## Score definitions

Alignment (parity with spatial heatmaps): on `nvl_obj`, if `nvl_nearest_hist_locus == 'a'` (fam on right), rotate spot xy 180° about arena center so **fam is left / nvl is right**. Midline = arena center `cx`.

| Token | Formula (valid frames only) | Range / sign |
|-------|-----------------------------|--------------|
| `frac_nvl_side` | `#(x_aligned > cx) / n_valid` | [0, 1]; share on nvl half |
| `mean_signed_x_m` | `mean((x_aligned − cx) / ppm)` | meters; **+** = toward nvl (right) |

**Not computed as primary:** `(nvl − fam) / (nvl + fam)` — that is DR rebrand. `frac_fam_side` may appear as descriptive companion only (`x < cx` share); it is **out of the BH family**.

## Grain / design

- Grain: `animal × session × nvl_obj`  
- Association: independent groups — Kruskal–Wallis on `condition` ∈ {noSD, GHSD, RBSD} **within sex**  
- Sessions in family: `NOR_BL`, `NOR_TX`, `NOR_REC3hr`, `NOR_REC11hr`  
- Source: NOR H5 spot xy (nose/neck/spine mean); **no kpMS** (portable; no model consensus needed)

## BH Family SideMass-A (locked)

| Axis | Levels |
|------|--------|
| metric | `frac_nvl_side`, `mean_signed_x_m` |
| session | 4 phases above |
| sex | F, M |

**Family size:** 2 × 4 × 2 = **16** Kruskal cells.  
**Hit rule:** `hit_fdr05` ⇔ `q_bh < 0.05` within this family only.  
**Pass:** ≥1 `hit_fdr05` **and** claim language ties the hit to recognition geometry (prefer `NOR_TX` / recovery sessions over BL-only).  
**Fail:** zero FDR hits → stop; do not invent Family B on the same xy without user OK.

## What this is not

- Not object-prox DR / `frac_near_nvl` (already audited).  
- Not object-appearance engagement Δ ([[V Engagement Delta]] side claim).  
- Not pooled spatial heatmaps (those stay D-only).  
- Not bout grammar (option B in handoff — separate contract if needed).

## Related

- [[V Candidate Lattice Null]] — spatial blocked until this exists  
- [[Run Syllable Spatial Heatmaps]] — alignment precedent  
- [[NOR IMPRESS Index]]
