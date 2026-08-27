# ADR 0007: Ambiguous token QC (prototype-level bout speed IQR)

## Status

Accepted (2026-06-22, grill session)

## Context

Some syllable prototypes may be kinematically bimodal (one raw id, two behaviors). Phase II tier assignment should not force a locomotion class on incoherent prototypes. `cluster_inequality.csv` flags cluster-level spread but is too blunt to exclude single outlier syllables.

## Decision

- Mark a behavior token **`ambiguous`** at the **prototype level** using bout-level diagnostics: e.g. IQR of per-bout mean speed for that `(seed, raw_id)` (and optionally heading), compared to a threshold.
- Thresholds are set during the same histogram calibration pass as Phase II tier YAML (ADR 0005); ship conservative defaults until reviewed.
- Ambiguous tokens are excluded from tier assignment but remain in Phase I tables; Phase III may split, merge, or name them after exemplar QC.
- Cluster-level inequality (`speed_range` in `cluster_inequality.csv`) remains a **diagnostic plot**, not the primary exclusion rule.

## Consequences

- Phase I pipeline grows a per-prototype `bout_speed_iqr` (or similar) column in labels/sidecar.
- Block ethograms need an `ambiguous` color or filter policy for tier-colored exports.
- Implementation extends `collect_syllable_kinematics` or a post-pass over bout instances.

## Alternatives considered

- **Cluster-level gate:** Excludes all tokens in a heterogeneous cluster.
- **No gate v1:** Risks mis-tiered tokens propagating to publication plots.
