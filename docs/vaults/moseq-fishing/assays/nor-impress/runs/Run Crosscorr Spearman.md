---
title: Run Crosscorr Spearman
type: run
assay: nor-impress
status: lava
claim_kind: na
verdict: pass
tags:
  - claim/run
  - assay/nor-impress
  - lava
---
# Run Crosscorr Spearman

**Status:** computed — between-animal behavior × physio Spearman screens. #ladder / #lava  
**Parent:** [[H Physio Coupling]]

## Intent

Spearman association screens under `sack/crosscorr/`. Primary DR×physio screen null/sparse; engagement-Δ follow-up also null for locked M cells.

## Links

- Hypothesis: [[H Physio Coupling]]
- Verdicts: [[V DR Physio Null]] · [[V Engagement Physio Null]]
- Behavior upstream: [[Run Condition on Paired Delta]] (engagement Δ)

## Artifacts

**Campaign root:** `sack/crosscorr/` ([[Campaign Roots]])

| Folder / file | Role |
|---------------|------|
| `out_spearman_physio_x_bh/` (`tables/spearman_long.csv`, README) | Canonical DR×physio BH screen — [[V DR Physio Null]] |
| `out_spearman_engagement_delta_physio/` | M×locked engagement Δ × physio — [[V Engagement Physio Null]] |
| `out_spearman_cluster13_bl_rec11/` | Clean zero FDR (keep as negative) |
| `out_spearman/` (cohort) | Demote — tiny-n \|ρ\|=1 cells ([[Prune Map]]) |
| `out_spearman_moseq_physio/` | Demote — alphabet fishing |

**Regen (engagement):** from `sack/crosscorr` — `.venv\Scripts\python.exe -m sack_crosscorr.engagement_physio_spearman`

## Related

- [[V DR Physio Null]] · [[V Engagement Physio Null]] · [[H Physio Coupling]] · [[Prune Map]]
