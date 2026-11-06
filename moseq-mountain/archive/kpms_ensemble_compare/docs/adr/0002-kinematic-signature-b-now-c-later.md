# ADR 0002: Phase I kinematic signature (scalars now, pose-shape later)

## Status

Accepted (2026-06-22, grill session)

## Context

Phase I behavior tokens need a feature bundle available without new pose pipelines. Legacy ambulation provides `is_moving` and `speed_mps`; kpMS provides bout-level speed and heading curves.

## Decision

**Scalars now:** Cluster on bout curves (speed + heading) as today. Attach scalar aggregates per syllable prototype for Phase II tier rules and QC: `mean_speed_mps`, `frac_still` (from `is_moving`), mean absolute heading change, `global_occupancy`. Do not add pose-shape features until Phase III.

**Pose-shape later:** Add body extension, head–tail angle, keypoint PCA when Phase III naming requires them.

**`is_moving` caveat:** Treat `frac_still` as provisional. `is_moving` is `debounce(speed > threshold)` with fixed parameters not tuned on this cohort. When `frac_still` and `mean_speed_mps` disagree, flag in bout-level diagnostics; Phase II tier rules weight speed over the still flag.

## Consequences

- `hdbscan_labels.csv` / sidecar grows scalar columns; clustering input unchanged initially.
- A future ambulation retune does not invalidate tokens if clustering stays curve-based; scalars refresh cheaply.
- Phase II locomotion tiers should be expressible primarily from anatomical `mean_speed_mps` and heading-change rate.

## Alternatives considered

- **Curves only:** Simpler but weak on still vs slow for tier rules.
- **Pose-shape in Phase I:** Blocks token stability on feature engineering.
