---
title: Run Syllable Spatial Heatmaps
type: run
assay: nor-impress
status: ladder
claim_kind: na
verdict: fail
tags:
  - claim/run
  - assay/nor-impress
  - ladder
---
# Run Syllable Spatial Heatmaps

**Status:** computed — D-only spatial pools. #ladder  
**Parent:** candidate geometry for [[H Recognition Separators]] / [[H Investigation Quality]]

## Intent

Syllable spatial heatmaps at recognition (`nvl_obj`). Per-animal side-mass I lives on [[Run Side Mass]] and **fails** FDR ([[V Side Geometry Null]]).

## Links

- Hypotheses: [[H Recognition Separators]] · [[H Investigation Quality]]
- I cousin: [[Run Side Mass]] · [[V Side Geometry Null]]
- Deck alphabet cousin: [[Run DR Framed Deck Exemplar]]

## Artifacts

**Campaign roots** (see [[Prune Map]]; exemplar folder is alphabet-bound):

| Folder | Role |
|--------|------|
| `…/_nor_object_mi/syllable_spatial_heatmaps/` | Primary multi-model D pools |
| `…/_nor_object_mi/syllable_spatial_heatmaps_cluster13_condition_overlay/` | Overlay cousin |
| `…/_nor_object_mi/syllable_spatial_heatmaps_exemplar_paramscan_s1-1e7_s2-3e4_ss-100/` | **Exemplar** — single model; recognition only; **tx overlay** (1 map per session × sex; color = condition) |

| File | Role |
|------|------|
| `fig_syllable_spatial_*__all_tx.png` | D mashups (exemplar) |
| `fig_syllable_spatial_condition_legend.png` | tx swatches |
| `grain_*__all_tx.json` | n / rot180 / loci / `dwell_s_by_tx` |
| `INFO_syllable_spatial_heatmaps.md` | Data dictionary |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/fig_syllable_spatial_heatmap.py` (`--overlay-tx`)

### Exemplar knobs (2026-10-09)

- **Model:** `paramscan_s1-1e7_s2-3e4_ss-100` (`n_models=1`)
- **Trial:** `nvl_obj` only
- **Sessions:** `NOR_BL`, `NOR_TX`, `NOR_REC3hr`, `NOR_REC11hr` × `F`/`M` → 8 maps
- **Color:** condition / tx (`noSD` green, `GHSD` orange, `RBSD` purple); all syllables (`keep_clusters=all`)

## Related

- [[Run Nearest Prox MI]] · [[Run Object Prox DR]] · [[Run Side Mass]] · [[Run DR Framed Deck Exemplar]]
