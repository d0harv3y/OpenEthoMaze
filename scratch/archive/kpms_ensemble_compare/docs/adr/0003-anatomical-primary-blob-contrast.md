# ADR 0003: Anatomical-primary tokens with blob contrast

## Status

Accepted (2026-06-22, grill session)

## Context

Three kpMS streams (anatomical, blob, fused) are fit separately. Raw syllable IDs do not cross streams. The lab expects anatomical pose to anchor behavior names, but blob centroid motion may discriminate freezing (globally still) from grooming (local motion, low centroid displacement).

## Decision

- **Authoritative behavior tokens** come from **anatomical** per-stream clustering only (Phase I).
- **Blob** scalars are joined to the same `(seed, raw_syllable_id)` prototypes for **cross-stream contrast** (Phase III grooming vs freezing), not for a second token table.
- **Fused** stream clustering runs as **validation** — contrasts that replicate on fused are higher confidence.

Publication block ethograms and treatment stats use anatomical tokens/tiers only.

## Consequences

- Phase I pipeline emits anatomical tokens plus blob/fused scalar sidecars keyed by `(seed, raw_id)` with contrast columns (e.g. speed delta anatomical−blob).
- Per-stream clustering still runs on all three streams; only anatomical `shared_cluster_id` maps to behavior tokens in exports.
- Phase III grooming vs freezing hypotheses lean on anatomical still + blob local-motion divergence, not `is_moving` alone.

## Alternatives considered

- **Per-stream tokens only:** No explicit cross-stream contrast for still behaviors.
- **Unified 45-model pool:** Geometrically ill-posed across streams.
