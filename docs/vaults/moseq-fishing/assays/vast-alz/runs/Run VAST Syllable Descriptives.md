---
title: Run VAST Syllable Descriptives
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
# Run VAST Syllable Descriptives

**Status:** computed — VAST anatomical paramscan descriptives (D). #ladder  
**Assay:** [[VAST Alz Index]]

## Intent

Bout counts / duration ECDFs / median-duration heatmaps across the anatomical paramscan (ct=0.1 dropped → 18 models). Same ladder step as NOR descriptives; VAST strata only.

## Links

- Index: [[VAST Alz Index]]
- Pattern: [[Simpler-First Ladder Pattern]]
- Downstream: [[Run VAST Syllable Kinematics]] · [[Run VAST Syllable Signatures]]

## Artifacts

**Campaign root:** `D:\az-sd-vast_paramscan2026\_syllable_descriptives\` ([[Campaign Roots]])

| File | Role |
|------|------|
| descriptives tables / figures | D |
| INFO next to folder | Data dictionary |

**Runner:** `OpenEthoMaze/scratch/vast_moseq/regen_paramscan2026_descriptives.py` (also `regen_syllable_descriptives.py`)

## Related

- [[Run VAST Syllable Kinematics]] · [[Run VAST Syllable Signatures]] · [[VAST Alz Index]]
