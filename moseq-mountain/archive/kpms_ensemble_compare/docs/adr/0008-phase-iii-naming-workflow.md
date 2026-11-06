# ADR 0008: Phase III naming workflow (IIIa still pass, IIIb full ontology)

## Status

Accepted (2026-06-22, grill session)

## Context

Phase III requires human validation to attach ethological names. A full grid-movie pass over every behavior token is expensive. The lab's first hypothesis is freezing vs grooming among still-tier tokens, using anatomical–blob contrast.

## Decision

- **Phase IIIa (now):** Still-tier focus only. For each anatomical token assigned Phase II tier `still`, review 3–5 auto-picked exemplar bouts; assign `freeze` / `groom` / `other` / `unsure` in `still_behavior_labels.csv`. Pre-sort candidates using stored `delta_speed_ab` and fused validation flags.
- **Phase IIIb (later):** Full token tray — grid movies or overlays for **all** behavior tokens and tiers — once IIIa is stable and contrast thresholds are trusted.

Do not use syllable merge (`kpms_apply_syllable_merge`) as a substitute for token-based naming (see ADR 0001).

## Consequences

- IIIa deliverable: `still_behavior_labels.csv` with `token_id`, `tier`, `delta_speed_ab`, `proposed_class`, `reviewer_class`, `exemplar_trial_keys`.
- Exemplar picker script ranks bouts by contrast score and occupancy; reuses `kpms_review_artifacts` or overlay PNGs where possible.
- Phase IIIb is explicitly deferred; locomotion tier names suffice for non-still tokens until then.

## Alternatives considered

- **Full ontology day one (B only):** High review burden before freeze/groom hypothesis is tested.
- **Merge-first (C):** Bypasses cross-seed tokens; conflicts with phased ethogram plan.
