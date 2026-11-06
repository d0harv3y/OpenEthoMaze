# ADR 0002: Bout scalar feature table

## Status

Accepted (2026-06-24)

## Context

Prior work resampled bout curves to `T_s`/`T_max` and padded for HDBSCAN — leaks bout length and confounds clustering.

## Decision

Each **bout row** carries only scalars:

| Column group | Fields |
|--------------|--------|
| Identity | stream, seed, trial_key, raw_syllable_id, bout_index, row span |
| Means | `bout_mean_speed_mps`, `bout_mean_abs_dheading`, `bout_mean_blob_area_px2`; optional `bout_mean_heading_rad` when `include_heading_direction=true` |
| Within-bout spread | `bout_iqr_speed_mps`, `bout_iqr_abs_dheading`, `bout_iqr_blob_area_px2`; optional `bout_iqr_heading_rad` when flag set |
| Extent | `bout_frames` (and/or `bout_duration_s`) |
| Cluster | `cluster_id` from cohort HDBSCAN on z-scored mean+IQR+duration features (all seeds) |

No `feat_*` curve columns. No per-syllable prototype aggregation for clustering.

## Consequences

- Blob area computed per frame from `tracking/blob` polygon (`polygon_area`), aligned to kpMS rows, then aggregated within bout.
- Speed/heading from same aligned timeline as archived `movement_layer` pattern (legacy ambulation + pose heading — exact source locked in implementation ADR if split).
- HDBSCAN runs once on long bout table; `cluster_id` written back to table.

## Alternatives considered

- Curve + DTW clustering — deferred; scalars first.
- Per-seed HDBSCAN — rejected for cross-seed bout cluster comparability.
