# ADR 0001: Three-stage ethogram pipeline

## Status

Accepted (2026-06-24, grill greenfield)

## Context

Frame-level kpMS syllables mix multiple behaviors per syllable id. Prototype clustering on syllable prototypes over-claims behavioral identity. A bout-level sticky HMM on hand-rolled features worked but does not share inference with kpMS.

## Decision

Adopt a **three-stage** pipeline:

1. **Stage I** — existing anatomical kpMS fit/apply (frame syllables).
2. **Stage II** — bout feature table (scalar kinematics per bout) + cohort HDBSCAN → `cluster_id` on each bout row.
3. **Stage III** — `jax_moseq.models.arhmm` sticky HDP AR-HMM on bout sequences (`data["x"]` = feature trajectory per trial, batched like kpMS). Decoded bout states = **behavior token** candidates.

Stage III uses the **same transition machinery** as kpMS (`resample_hdp_transitions`, `kappa`, `alpha`, `gamma`) but **not** `keypoint_slds` (no keypoints, centroid, heading SLDS blocks).

## Consequences

- Scratch greenfield under `scratch/behavior_ethogram/`; prior `kpms_ensemble_compare` archived.
- New fit/apply CLI or scripts for Stage III; does not replace `maze-kpms-fit`.
- `latent_dim` = bout feature dimension; `nlags` tuned for bout timescale (likely 1–3, not 5).
- κ scale must be recalibrated for **bout** steps, not video frames.

## Alternatives considered

- Plain EM Gaussian HMM (prototype) — rejected; not kpMS-family, no HDP.
- HDBSCAN cluster as final token — rejected; no temporal model.
- Refit keypoint_slds on bout pseudo-observations — rejected; wrong generative model.
