---
title: V Near Misses Watchlist
type: verdict
assay: nor-impress
status: rabbit-hole
claim_kind: mixed
verdict: na
tags:
  - claim/verdict
  - assay/nor-impress
  - rabbit-hole
  - mixed
aliases:
  - Q5 Near Misses
---
# V Near Misses Watchlist

**Date:** 2026-09-23  
**Rule (lab):** a cell is a **near miss** when `p < 0.05` **and** `0.1 < q_bh < 0.2` inside its **declared** BH family.

**Not a lock.** Near miss ≠ `hit_fdr05`. Do not slide these as condition separators. Do not reopen physio on them. Useful as a **watch list** / direction inventory only.

**Acronyms:** BH = Benjamini–Hochberg; FDR = false-discovery rate; NOR = novel object recognition; DR = discrimination ratio.

## Catalog (declared families only)


| Family                 | Source honesty / run                                  | sex | session / step | metric                 | p      | q_bh      | median noSD / GHSD / RBSD  |
| ---------------------- | ----------------------------------------------------- | --- | -------------- | ---------------------- | ------ | --------- | -------------------------- |
| Candidates occupancy A | [[V Candidate Lattice Null]] / [[Run Object Prox DR]] | M   | `NOR_TX` level | `frac_near_nvl`        | 0.030  | **0.121** | 0.274 / 0.201 / 0.127      |
| OccSessDelta-A         | [[V Occupancy Delta Null]]                            | M   | `BL→TX`        | `delta_frac_near_nvl`  | 0.034  | **0.135** | +0.038 / +0.038 / −0.018   |
| SideMass-A             | [[V Side Geometry Null]]                              | F   | `NOR_TX`       | `frac_nvl_side`        | 0.0067 | **0.107** | 0.698 / 0.595 / 0.592      |
| SideMass-A             | [[V Side Geometry Null]]                              | F   | `NOR_TX`       | `mean_signed_x_m`      | 0.015  | **0.121** | +0.053 / +0.033 / +0.027 m |
| BoutGrammar-A          | [[V Visit Grammar Null]]                              | F   | `NOR_REC11hr`  | `mean_nvl_visit_dur_s` | 0.0072 | **0.174** | 2.88 / 4.39 / 2.34 s       |

**n = 5** near misses (2026-09-23).

## Pattern (descriptive only)

- **Males, novel-prox occupancy:** TX **level** and BL→TX **Δ** both near-miss — noSD ≥ GHSD > RBSD (RBSD Δ slightly negative). Same biology twice; neither FDR-locks.
- **Females, geometry at challenge:** SideMass nvl-side share / signed midline bias near-miss at `NOR_TX` — noSD more nvl-side than SD arms.
- **Females, recovery visit duration:** BoutGrammar mean nvl-visit duration near-miss at `NOR_REC11hr` only (not TX) — GHSD longest median; not a challenge-preference claim.

None of these are DR / preference. Engagement Δ ([[V Engagement Delta]]) remains the only locked condition separator (non-recognition).

## Explicitly **not** near misses (common traps)

| Cell | Why out |
|------|---------|
| M TX `n_nvl_entries` (BoutGrammar) p≈0.035, q≈0.42 | q ∉ (0.1, 0.2) |
| F TX `delta_frac_near_nvl` p≈0.074 | p ≥ 0.05 |
| four_mask primary min p≈0.055, q≈0.19 | p ≥ 0.05 |
| Candidates Q4 family M `frac_near_nvl` q≈0.48 | q ∉ (0.1, 0.2) |
| Any `hit_fdr05` | already a pass, not a near miss |

## How to cite

> Near miss under rule `p < 0.05` and `0.1 < q_bh < 0.2` in family *X* — **not** FDR-locked; see [[V Near Misses Watchlist]].

## Figure

Visit-grammar honesty panel (includes F REC11 visit-duration near miss).

![[fig_v_visit_grammar_null.svg]]

Side-mass honesty panel (includes F TX near misses).

![[fig_v_side_geometry_null.svg]]

Occupancy-Δ honesty panel (includes M novel-Δ near miss).

![[fig_v_occupancy_delta_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[H Recognition Separators]]
- [[V Candidate Lattice Null]]
- [[V Side Geometry Null]]
- [[V Visit Grammar Null]]
- [[V Occupancy Delta Null]]
- [[NOR IMPRESS Index]]

#rabbit-hole
