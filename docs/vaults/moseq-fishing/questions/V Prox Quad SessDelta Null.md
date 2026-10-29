---
title: V Prox Quad SessDelta Null
type: verdict
assay: nor-impress
status: lava
claim_kind: mixed
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
  - mixed
aliases:
  - Litmus sessΔ Prox Quad Session Delta
---
# V Prox Quad SessDelta Null

**Date:** 2026-10-06  
**Scope:** [[Run Prox Quad Session Delta]] — Litmus sessΔ for [[F QuadComp-A]] / [[F ProxComp-A]] (and time / level companions).  
**Claim kinds:** composition `#alphabet-bound`; `dr_time_*` `#clock-portable`.  
**Exploratory figure packs** (Shannon / richness / Hill q=2; pooled + per-animal): [[Run Prox Quad Session Step Figs]] — do not confuse with this sealed BH.

## Verdict

| Layer | Result |
|-------|--------|
| Wilcoxon Δ vs 0 (protocol dynamics) | **hits** — esp. BL→TX time twins; richness DR cousins; some level Δ |
| Kruskal Δ × `condition` (difference-of-differences) | **fail** — 0 FDR across all steps (Quad-SessDelta / Prox-SessDelta BH within step) |

Litmus sessΔ does **not** unlock a condition separator. Dynamics exist; condition does not modulate them under the declared BH.

## Headline step: BL→TX (sex=all Wilcoxon)

| Board     | Metric              | n    | med Δ | p      | hit |
| --------- | ------------------- | ---- | ----- | ------ | --- |
| Quad      | `dr_time_quad`      | 133  | +0.16 | 1.8e-4 | yes |
| Prox      | `dr_time_prox`      | 129  | +0.24 | 3.5e-7 | yes |
| Quad      | `dr_richness_quad`  | 131  | +0.05 | 0.023  | yes |
| Prox      | `dr_richness_prox`  | 126  | +0.10 | 9e-4   | yes |
| Quad      | `dr_shannon_quad`   | 131  | ≈0    | 0.87   | no  |
| Prox      | `dr_shannon_prox`   | 126  | ≈0    | 0.99   | no  |
| Quad      | `nvl_shannon_quad`  | 131  | −0.23 | 1.3e-4 | yes |
| Prox      | `nvl_shannon_prox`  | 126  | −0.22 | 0.0057 | yes |
| Prox      | `nvl_richness_prox` | 126  | +1    | 0.042  | yes |
| Quad/Prox | `fam_richness_*`    | ~130 | −1    | ≤0.016 | yes |

Pattern: time preference for novel **rises** BL→TX; novel-ball Shannon **falls**; fam richness drops a notch. Shannon DR cousins stay flat (both sides move).

## Δ × condition (BL→TX Kruskal; BH within board×step)

**0/28** `hit_fdr05` at BL→TX (14 Quad + 14 Prox cells). Best near-miss: Quad M `fam_richness_quad` p≈0.0086 → q≈0.120 (watchlist only — not promoted).

Other steps (TX→REC*, BL→REC*): also **0 FDR**. Lone uncorrected p05 cells do not survive BH.

## Locked language

> Within-animal session Δ of Quad/Prox DR cousins, time twins, and fam/nvl Shannon–richness levels show protocol dynamics (esp. BL→TX rise in `dr_time_*` and richness DR). Condition does **not** modulate those Δ under Quad-SessDelta / Prox-SessDelta BH (0 FDR all steps).

## Evidence

| Artifact | Finding |
|----------|---------|
| `session_delta_wilcoxon_long.csv` | 102 `hit_p05` across steps×boards (uncorrected dynamics) |
| `session_delta_kruskal_long.csv` | **0** `hit_fdr05` |
| `run_summary.json` | `kruskal_n_hit_fdr05: 0` |

→ [[Run Prox Quad Session Delta]]

## Related

- [[V QuadComp Null]] · [[V ProxComp Null]] — litmus T1-assay/T1
- [[V Occupancy Delta Null]] — classic occupancy BL→TX cousin (also 0 FDR)
- [[H Investigation Quality]] · [[H Recognition Separators]]
- [[F ProxComp-A Score Contract]] § C
