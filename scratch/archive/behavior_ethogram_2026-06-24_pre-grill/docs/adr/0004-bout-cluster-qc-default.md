# ADR 0004: Bout cluster role in Stage III

## Status

Accepted (2026-06-24)

## Context

Stage II assigns each bout an HDBSCAN `cluster_id`. Stage III AR-HMM must decide whether that label is an input feature or a parallel diagnostic.

## Decision

- **Default (`include_cluster_feature=false`):** `cluster_id` is **QC and visualization only**. Stage III AR-HMM `data["x"]` uses kinematic scalars only (speed, heading, blob area means and IQRs, duration).
- **Optional (`include_cluster_feature=true`):** append normalized or one-hot `cluster_id` to `data["x"]` for ablation — not the publication default.

Behavior tokens remain **AR-HMM decoded states**, never raw `cluster_id`.

## Consequences

- `fit_bout_arhmm.py` (or equivalent) exposes `--include-cluster-feature` default false.
- Diagnostics: per-state cluster occupancy, boundary agreement AR state vs cluster runs.

## Alternatives considered

- **B only** — rejected; couples two unsupervised layers by default.
- **C: cluster replaces AR-HMM** — rejected; no temporal model.
