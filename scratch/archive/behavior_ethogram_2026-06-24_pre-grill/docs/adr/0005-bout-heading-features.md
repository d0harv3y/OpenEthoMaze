# ADR 0005: Bout heading features

## Status

Accepted (2026-06-24)

## Context

“Heading” can mean turning rate (path curvature) or absolute facing direction. They answer different ethological questions.

## Decision

- **Default (`include_heading_direction=false`):** `bout_mean_abs_dheading` and `bout_iqr_abs_dheading` only (mean absolute Δheading per frame within bout).
- **Optional (`include_heading_direction=true`):** also `bout_mean_heading_rad` (circular mean) and `bout_iqr_heading_rad` for spatial-facing ablations.

Heading source: anatomical pose heading on kpMS-aligned rows (same timeline as speed and blob area).

## Consequences

- Default AR-HMM / HDBSCAN feature dimension stays smaller (7 kinematic + duration fields).
- `compile_bout_features.py` exposes `--include-heading-direction` default false.

## Alternatives considered

- **Circular mean only (B)** — rejected; weak for turn-heavy vs transit without turning rate.
- **Both always (C)** — deferred to flag; not default columns.
