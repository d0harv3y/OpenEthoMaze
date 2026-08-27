# ADR 0009: Defer Phase III human naming

## Status

Accepted (2026-06-24)

## Context

Prior plan had Phase IIIa (still behaviors: freeze/groom) then IIIb (full ontology). Cross-stream contrast is out of scope; cohort is still growing toward a single-model fit.

## Decision

**Defer Phase III** (human `pose label` assignment, exemplar QC CSVs, grid movies for naming).

Ship through:

- Stage I — anatomical kpMS syllables  
- Stage II — bout scalar table + cohort HDBSCAN `cluster_id`  
- Stage III — bout AR-HMM behavior tokens  
- **Locomotion tiers** — YAML rules on behavior-token centroids (histogram calibration as before)

Naming workflow (IIIa/IIIb or flat) revisited when single-model cohort fit stabilizes.

## Consequences

- No `still_behavior_labels.csv` or naming kit in first implementation slice.
- `CONTEXT.md` retains **named behavior** / **pose label** terms for future use.
- Exports use behavior-token id + locomotion tier + optional cluster_id for QC.

## Alternatives considered

- **IIIa revised without cross-stream (A)** — deferred with full Phase III.
- **Flat naming pass (B)** — deferred.
