---
title: Run VAST Syllable Kinematics
type: run
assay: vast-alz
status: ladder
claim_kind: na
verdict: na
tags:
  - claim/run
  - assay/vast-alz
  - ladder
---
# Run VAST Syllable Kinematics

**Status:** infrastructure — ADR-0005 / 9-D bout kinematics on VAST run-interval bouts. #ladder  
**Assay:** [[VAST Alz Index]]

## Intent

Pose join from VAST legacy H5 (`animal → session → trial`). Ladder step per [[Simpler-First Ladder Pattern]] (VAST strata only).

## Links

- Upstream: [[Run VAST Syllable Descriptives]]
- Downstream: [[Run VAST Syllable Signatures]]

## Artifacts

**Campaign root:** `D:\az-sd-vast_paramscan2026\_syllable_bout_kinematics\` ([[Campaign Roots]])

| File | Role |
|------|------|
| kinematics bout table | D — ADR-0005 features |
| INFO next to folder | Data dictionary |

**Runner:** `OpenEthoMaze/scratch/vast_moseq/regen_paramscan2026_kinematics.py` (also `regen_syllable_bout_kinematics.py`)

## Related

- [[Run VAST Syllable Descriptives]] · [[Run VAST Syllable Signatures]] · [[Simpler-First Ladder Pattern]] · [[VAST Alz Index]]
