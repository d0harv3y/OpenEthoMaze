---
title: Run Per Animal Syllable Descriptives
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
# Run Per Animal Syllable Descriptives

**Status:** computed — accent / alphabet QC (D). #ladder #alphabet-bound  
**Parent:** [[H Alphabet Equating]]

## Intent

Median bout duration heatmaps: y = animal×κ₂, x = within-model frequency rank. **18** panels = sex × condition × `num_states`. Not alphabet equating; not condition I.

## Links

- Hypothesis: [[H Alphabet Equating]]
- Parent campaign: [[Run Per Animal Paramscan]]
- Claim kind: **#alphabet-bound** (animal-local syllable inventories)

## Artifacts

**Campaign root:** `sack/datas/impress/nor_per_animal_paramscan/_syllable_descriptives/` ([[Campaign Roots]])

| File | Role |
|------|------|
| duration heatmaps / tables | D — accent QC |
| `INFO_syllable_descriptives.md` | Data dictionary |

### Figures

| File | Role | Claim kind |
|------|------|------------|
| `figures/fig_median_bout_dur_sex-{F,M}_tx-{noSD,GHSD,RBSD}_ss-{50,75,100}.svg` | 18 accent QC heatmaps | #alphabet-bound |
| `figures/FIGURES.md` | Full inventory | — |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/per_animal_descriptives_qc.py`

## Related

- [[Run Per Animal Paramscan]] · [[H Alphabet Equating]] · [[Claim Kind]]
- [[Run Slides Pack]] (pooled descriptives cousin)
