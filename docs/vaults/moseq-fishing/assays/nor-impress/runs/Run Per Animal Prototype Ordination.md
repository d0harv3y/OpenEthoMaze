---
title: Run Per Animal Prototype Ordination
type: run
assay: nor-impress
status: ladder
claim_kind: alphabet-bound
verdict: na
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - alphabet-bound
---
# Run Per Animal Prototype Ordination

**Status:** computed — flat vs stage-1 kinematic remapping bearings (D). #ladder #alphabet-bound  
**Parent:** [[H Alphabet Equating]]

## Intent

Z-score 9 kinematic columns → HDBSCAN → PCA (feature-space ordinate, not PCoA). HDBSCAN knobs still exploratory.

## Links

- Upstream: [[Run Per Animal Syllable Kinematics]]
- Hypothesis: [[H Alphabet Equating]]
- Pooled cousin: [[Run Syllable Signatures]]
- Claim kind: **#alphabet-bound** (remapping infrastructure)

## Artifacts

**Campaign root:** `sack/datas/impress/nor_per_animal_paramscan/_nor_object_mi/simpler_first_prototype_ordination/` ([[Campaign Roots]])

| File | Role |
|------|------|
| ordination tables | D — flat vs stage-1 |
| `INFO_prototype_ordination.md` | Data dictionary |

### Figures

| File | Role | Claim kind |
|------|------|------------|
| `figures/fig_prototype_ordination_flat.svg` | Flat HDBSCAN + PCA | #alphabet-bound |
| `figures/fig_prototype_ordination_stage1.svg` | Stage-1 (within-animal then across) | #alphabet-bound |
| `figures/fig_prototype_pca3d_flat_vs_stage1.svg` | 3D compare | #alphabet-bound |
| `figures/prototype_pca3d_across_mcs4_ms2.html` | Interactive 3D | #alphabet-bound |
| `figures/FIGURES.md` | Full inventory | — |

**Runners:** `OpenEthoMaze/scratch/nor_object_mi/per_animal_prototype_ordination.py` · `…_plotly3d.py`

## Related

- [[Run Per Animal Syllable Kinematics]] · [[Run Syllable Signatures]] · [[H Alphabet Equating]] · [[Run Per Animal Paramscan]] · [[Claim Kind]]
