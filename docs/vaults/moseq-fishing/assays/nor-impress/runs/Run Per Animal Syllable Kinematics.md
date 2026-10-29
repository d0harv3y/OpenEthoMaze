---
title: Run Per Animal Syllable Kinematics
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
# Run Per Animal Syllable Kinematics

**Status:** infrastructure — ADR-0005 on animal-local alphabets. #ladder  
**Parent:** [[H Alphabet Equating]] · feeds [[Run Per Animal Prototype Ordination]]

## Intent

One row = bout × animal-local model. Full 144 × 9 (~1.22M bouts; absorb `<3`). `raw_syllable_id` is animal×model-local.

## Links

- Parent: [[Run Per Animal Paramscan]]
- Downstream: [[Run Per Animal Prototype Ordination]]
- Pooled cousin: [[Run Syllable Kinematics]]

## Artifacts

**Campaign root:** `sack/datas/impress/nor_per_animal_paramscan/_nor_object_mi/simpler_first_syllable_kinematics/` ([[Campaign Roots]])

| File | Role |
|------|------|
| kinematics bout table | D — ADR-0005 features |
| `INFO_syllable_kinematics.md` | Data dictionary |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/per_animal_syllable_kinematics.py --clean`

## Related

- [[Run Per Animal Paramscan]] · [[Run Syllable Kinematics]] · [[Run Per Animal Prototype Ordination]] · [[H Alphabet Equating]]
