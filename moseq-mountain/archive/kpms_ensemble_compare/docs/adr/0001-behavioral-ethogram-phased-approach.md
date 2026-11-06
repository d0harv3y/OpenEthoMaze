# ADR 0001: Phased behavioral ethogram (I → II → III)

## Status

Accepted (2026-06-22, grill session). Renamed from C→A→B to Roman numerals 2026-06-22.

## Context

kpMS syllable IDs are not comparable across seeds. The lab wants interpretable behaviors (freezing, grooming, sprinting, …) rather than arbitrary id numbers. Available kinematics today are mainly legacy ambulation (`is_moving`, speed) plus kpMS heading/centroid per row.

## Decision

Deliver the behavioral ethogram in three phases:

1. **Phase I — Behavior tokens:** Pool kinematic signatures across seeds on anatomical prototypes; assign stable token indices; store scalar sidecars and cross-stream contrast. No human names.
2. **Phase II — Locomotion tiers:** Group tokens into coarse locomotion classes falsifiable from anatomical features (still / slow / fast / turn-heavy).
3. **Phase III — Named behaviors:** Attach human labels (freeze, groom, probe, …) via exemplar QC; split still tokens using anatomical–blob contrast and fused validation.

Do not skip to Phase III by renaming syllable ids or speed-rank indices.

## Consequences

- Cross-seed per-stream clustering is the foundation for Phase I, not per-seed id tables alone.
- Block ethogram exports can show token/tier colors before named behaviors exist.
- Grooming vs freezing requires cross-stream contrast and/or pose geometry in Phase III; ambulation spot XY alone is insufficient in Phase II.
- Phase I tokens attach to **syllable prototypes** only; bout-level stats (`cluster_inequality.csv`) are QC gates, not the clustering unit.

## Alternatives considered

- **Phase II first:** Fast plots but no cross-seed stability; tiers would differ per seed.
- **Phase III first:** High risk of false confidence; speed bins conflate ethologically distinct still behaviors.
