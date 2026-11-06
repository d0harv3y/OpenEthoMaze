# ADR 0004: Cross-stream contrast timing (store Phase I, act Phase III)

## Status

Accepted (2026-06-22, grill session)

## Context

Anatomical–blob kinematic contrast may separate freezing (still on both streams) from grooming (local anatomical motion, low blob displacement). The phased plan separates locomotion tiers (Phase II) from named behaviors (Phase III).

## Decision

- **Phase I:** Compute and store cross-stream contrast scalars per syllable prototype (`mean_speed_mps` per stream, `delta_speed_ab`, fused validation flags). Do not classify grooming vs freezing yet.
- **Phase II:** Assign locomotion tiers from **anatomical scalars only** (still / slow explore / fast transit / turn-heavy). Do not split still into frozen vs grooming.
- **Phase III:** Split **still-tier** tokens using stored contrast + exemplar QC; fused stream confirms or flags ambiguous cases.

## Consequences

- Phase II block ethograms stay simple and falsifiable before ethological naming commitments.
- Phase III starts from a pre-built contrast table, not ad-hoc per-review joins.
- Implementation: contrast join script after per-stream clustering on all three streams.

## Alternatives considered

- **Split still in Phase II:** Risks wrong grooming/freeze thresholds before video QC.
- **Contrast only at Phase III ad hoc:** Recomputes joins repeatedly; loses audit trail.
