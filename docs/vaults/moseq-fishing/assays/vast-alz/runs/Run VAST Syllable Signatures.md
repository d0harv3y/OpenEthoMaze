---
title: Run VAST Syllable Signatures
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
# Run VAST Syllable Signatures

**Status:** infrastructure — HDBSCAN kinematic prototypes on VAST. #ladder  
**Assay:** [[VAST Alz Index]]

## Intent

Prototype kinematics + HDBSCAN `cluster_id` remap across models. Pause focus for DA overlays is cohort-specific (paramscan2026: cluster **40**).

## Links

- Upstream: [[Run VAST Syllable Kinematics]]
- Downstream: [[Run VAST Trial Session Step DA]]

## Artifacts

**Campaign root:** `D:\az-sd-vast_paramscan2026\_syllable_signatures\` ([[Campaign Roots]])

| File | Role |
|------|------|
| prototype / cluster tables | D — HDBSCAN remap |
| INFO next to folder | Data dictionary |

**Runner:** `OpenEthoMaze/scratch/vast_moseq/regen_paramscan2026_signatures.py` (also `regen_syllable_signatures.py`)

## Related

- [[Run VAST Syllable Kinematics]] · [[Run VAST Trial Session Step DA]] · [[Simpler-First Ladder Pattern]] · [[VAST Alz Index]]
