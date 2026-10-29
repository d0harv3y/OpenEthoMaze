---
title: Run Nearest Prox MI
type: run
assay: nor-impress
status: ladder
claim_kind: na
verdict: na
tags:
  - claim/run
  - assay/nor-impress
  - ladder
---
# Run Nearest Prox MI

**Status:** computed — syllable ↔ object-locus MI. #ladder  
**Parent:** [[H Investigation Quality]] · join candidate for [[H Recognition Separators]]

## Intent

Mutual information between syllable stream and nearest-object proximity stratum. Pick **one** locked tree (paramscan single model **or** ensemble) — not both.

## Links

- Hypothesis: [[H Investigation Quality]]
- Lattice: [[V Recognition Lattice Null]]
- Cousin: [[Run Info Dr Pause]]

## Artifacts

**Campaign roots** (pick one; see [[Prune Map]]):

| Folder | Role |
|--------|------|
| `…/_nor_object_mi/simpler_first_nearest_prox_mi__paramscan_s1-1e8_s2-1e5_ss-50/` | Locked single-model tree |
| `…/_nor_object_mi/simpler_first_nearest_prox_cluster_mi__ensemble/` | Ensemble cousin |

| File | Role |
|------|------|
| `mi_stratum_tests_long.csv` | I — `hit_fdr05` none; sparse uncorrected at BL/REC11 F |
| `INFO_nearest_prox_mi.md` | Data dictionary |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/` — nearest-prox-MI suite

## Related

- [[Run Info Dr Pause]] · [[Run Syllable Spatial Heatmaps]] · [[Prune Map]]
