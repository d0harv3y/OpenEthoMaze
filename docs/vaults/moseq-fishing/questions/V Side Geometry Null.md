---
title: V Side Geometry Null
type: verdict
assay: nor-impress
status: lava
claim_kind: clock-portable
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
  - clock-portable
aliases:
  - Q5 SideMass Honesty Pass
---
# V Side Geometry Null

**Date:** 2026-09-23  
**Scope:** [[Run Side Mass]] / Family SideMass-A (declared in [[E Side Geometry]] **before** peeking at q).  
**Gate:** Kruskal on `frac_nvl_side` / `mean_signed_x_m` by `condition` within sex × 4 phases; `hit_fdr05` within the 16-cell BH family.  
**Claim kind:** #clock-portable

## Verdict

**Fail.** Zero `hit_fdr05`. Closest cells: female `NOR_TX` `frac_nvl_side` (p≈0.0067 → q≈0.107) and `mean_signed_x_m` (p≈0.015 → q≈0.121). Same honesty zone as absolute `frac_near_nvl` (q≈0.12) — suggestive uncorrected, not FDR-locked.

Do **not** invent Family B on the same xy without user OK. Bout grammar (handoff option B) remains the next *new* score if the lab continues the recognition hunt.

## Near miss

F `NOR_TX` `frac_nvl_side` (q≈0.107) and `mean_signed_x_m` (q≈0.121) → [[V Near Misses Watchlist]]. Not FDR-locked.

## Locked negative language

> After fam-left alignment, per-animal nvl-side frame share and signed midline bias do **not** separate `noSD` / `GHSD` / `RBSD` under the pre-declared SideMass-A BH family (0/16 `hit_fdr05`). Female challenge `NOR_TX` shows the lowest uncorrected p values but q stays above 0.05.

## Evidence

Full paths + runner → [[Run Side Mass]].

| Artifact | Finding |
|----------|---------|
| `side_mass_tests_long.csv` | 16/16 finite p; **0** `hit_fdr05`; 2 `hit_p05` (both F, NOR_TX) |
| `side_mass_per_animal.csv` | 432 rows; 144 animals; 249 rot180 |
| `run_summary.json` | `pass_family_a: false` |

**Medians (F, NOR_TX, `frac_nvl_side`):** noSD ≈ 0.70; GHSD ≈ 0.59; RBSD ≈ 0.59 — directionally noSD more nvl-side, not FDR-kept.

**Males:** no Family A cell with p < 0.05 (best TX `mean_signed_x_m` p≈0.16).

## Keep / demote

| Item | Action |
|------|--------|
| SideMass-A runner + INFO | **Keep as negative** (geometry I now exists; claim fails) |
| Engagement Δ side claim | Unchanged — [[V Engagement Delta]] |
| Further SideMass BH re-cuts | **Stop** unless new contract |

## Figure

Honesty panel — SideMass-A. Source: [[Run Side Mass]].

![[fig_v_side_geometry_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[E Side Geometry]]
- [[H Recognition Separators]]
- [[V Candidate Lattice Null]]
- [[Run Side Mass]]
- [[NOR IMPRESS Index]]

#lava
