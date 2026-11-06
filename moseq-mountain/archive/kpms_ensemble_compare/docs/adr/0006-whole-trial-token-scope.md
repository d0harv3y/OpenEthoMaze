# ADR 0006: Whole-trial token scope (`phase=all`)

## Status

Accepted (2026-06-22, grill session)

## Context

Clustering supports `--phase all|run|iti`. RUN-only tokens match maze block ethograms but miss ITI behaviors (e.g. grooming). Separate per-phase tables double maintenance. The lab chose a single token set for the whole trial.

## Decision

- Phase I clustering and Phase II tier YAML use **`--phase all`** as the canonical token/tier table.
- Block ethogram exports continue to **filter display to RUN** (or other strata) at plot time; frame labels resolve syllable id → token via the whole-trial lookup table.
- Revisit separate `run` / `iti` token tables only if tier calibration or Phase III still-behavior splits prove inadequate on mixed-phase histograms.

## Consequences

- One `anatomical/shared/` artifact set per stream (not duplicated per phase suffix).
- Tier histogram calibration mixes ITI and RUN kinematics — interpret `still` tier as trial-wide stillness, not RUN-only.
- Grooming in ITI contributes to prototype scalars for syllables that also appear in RUN.

## Alternatives considered

- **RUN only (v1):** Cleaner locomotion tiers for maze analysis; loses ITI-contributed kinematics on shared syllables.
- **Separate run + iti tables:** Ethologically cleaner; rejected for lookup simplicity.
