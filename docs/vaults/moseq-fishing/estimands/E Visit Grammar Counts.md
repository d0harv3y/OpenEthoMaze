---
title: E Visit Grammar Counts
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
  - Q5 BoutGrammar Score Contract
---
# E Visit Grammar Counts

**Date:** 2026-09-23  
**Status:** declared → **computed** → [[V Visit Grammar Null]] **fail** (0/24 `hit_fdr05`). Do not expand after peeking at `q`.  
**Parent:** [[H Recognition Separators]] / [[H Investigation Quality]]  
**Run:** [[Run Bout Grammar]]

## One-line

Per-animal **novel-prox visit grammar** (contiguous near-nvl runs + still-near share) — not DR, not engagement Δ, not SideMass, not four_mask TX−BL ANOVA.

## Score definitions

Prox gate: frame has `dist_nvl_m < r` with **r = 0.10 m** (same radius as object-prox). Source: NOR H5 spot → fam/nvl centers (`role_distances_m`). **No kpMS / no `raw_syllable_id`.**

A **nvl visit** = maximal contiguous run of near-nvl frames (valid frames only; gaps of invalid break runs).

| Token | Formula | Notes |
|-------|---------|-------|
| `n_nvl_entries` | number of nvl visits | approach–leave count proxy |
| `mean_nvl_visit_dur_s` | mean(visit_frames / fps) | NaN if `n_nvl_entries = 0` |
| `frac_still_near_nvl` | `#(near_nvl ∩ immobile) / #near_nvl` | immobile = complement of `movement_bouts` on spot; NaN if no near frames |

**Out of family (descriptive only):** `total_nvl_near_s`, `median_nvl_visit_dur_s`, fam-prox cousins.

**Not this family:** `(nvl−fam)/(nvl+fam)` DR; SideMass midline share; four_mask `frac_mask` on TX−BL.

## Grain / design

- Grain: `animal × session × nvl_obj`  
- Association: independent groups — Kruskal–Wallis on `condition` within sex  
- Sessions: `NOR_BL`, `NOR_TX`, `NOR_REC3hr`, `NOR_REC11hr`  
- Design contrast vs four_mask: **level** Kruskal by condition (not TX−BL Δ × condition)

## BH Family BoutGrammar-A (locked)

| Axis | Levels |
|------|--------|
| metric | `n_nvl_entries`, `mean_nvl_visit_dur_s`, `frac_still_near_nvl` |
| session | 4 phases above |
| sex | F, M |

**Family size:** 3 × 4 × 2 = **24** Kruskal cells.  
**Hit rule:** `hit_fdr05` ⇔ `q_bh < 0.05` within this family.  
**Pass:** ≥1 `hit_fdr05` with recognition-linked claim language (prefer `NOR_TX` / recovery).  
**Fail:** zero FDR → stop; no Family B on the same scores without user OK.

## Related

- [[V Side Geometry Null]] — geometry fail  
- [[V Candidate Lattice Null]] — classic `t_nvl_s` / four_mask fail  
- [[H Investigation Quality]]  
- [[NOR IMPRESS Index]]
