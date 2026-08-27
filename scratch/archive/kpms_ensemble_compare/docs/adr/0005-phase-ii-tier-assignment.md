# ADR 0005: Phase II tier assignment (YAML default, histogram-calibrated target)

## Status

Accepted (2026-06-22, grill session)

## Context

Phase II locomotion tiers need a reproducible assignment rule on anatomical token scalars (`mean_speed_mps`, heading-change rate). The lab prefers data-driven cut points but has not yet inspected cohort histograms.

## Decision

1. **Ship default:** Hand-tuned thresholds in `locomotion_tiers.yaml` (priority-ordered rules on token centroids). Tokens failing QC (`cluster_inequality` speed_range too high) → `ambiguous`.
2. **Calibration gate:** Before replacing YAML defaults, produce histogram / scatter plots of token scalars from anatomical Phase I (`shared/hdbscan_labels_*.csv`) and review once on test2.
3. **Target state:** Data-driven tier boundaries (e.g. k-means or GMM on token scalars, or YAML thresholds set from histogram elbows) after calibration — not unsupervised tiers without human review of the plots.

Default to A until histograms are reviewed; B is the intended evolution, not day-one black-box clustering.

## Consequences

- First Phase II exports use documented YAML thresholds (reproducible, explainable).
- A small calibration script/notebook is part of Phase II, not optional polish.
- Tier boundaries may change once after histogram review; version the YAML (`locomotion_tiers_v1.yaml`).

## Alternatives considered

- **B only (unsupervised day one):** Tier boundaries shift opaquely; hard to publish.
- **C (speed_index quantiles):** Conflates speed rank with turning; not locomotion classes.
