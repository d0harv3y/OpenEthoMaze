# ADR 0003: Anatomical-only analysis scope

## Status

Accepted (2026-06-24)

## Context

Prior ethogram plan used anatomical + blob + fused kpMS streams for contrast and validation.

## Decision

- **kpMS fit/apply:** anatomical only.
- **Ethogram Stages II–III:** anatomical syllable bouts only.
- **Blob/fused kpMS streams:** dropped from this analysis track.
- **Blob polygon** in trial H5 may still supply **area scalars** on bout rows (backup tracker geometry, not a second kpMS model).

Cross-stream contrast, fused validation, and ensemble seed×stream matrices are out of scope until explicitly revived.

## Consequences

- Retire ADR 0003/0004 from archived `kpms_ensemble_compare` as superseded for this track.
- Cohort artifacts live under `behavior_ethogram/` without `blob/` or `fused/` stream subtrees for token tables.
