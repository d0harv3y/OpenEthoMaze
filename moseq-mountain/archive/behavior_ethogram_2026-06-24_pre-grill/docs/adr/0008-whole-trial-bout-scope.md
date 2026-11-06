# ADR 0008: Whole-trial bout scope

## Status

Accepted (2026-06-24)

## Context

Trials include ITI, run, and other labeled controller phases. Restricting bout features to RUN-only changes still/locomotion statistics and AR-HMM state occupancy.

## Decision

- Bout feature table and Stage III AR-HMM use **`all`** kpMS-aligned frames (ITI + run + other phases on the timeline).
- RUN-only (or other phase) filtering happens at **export and visualization** only — not a separate token table or refit by default.

## Consequences

- `bout_primary_state` remains on bout rows for stratified exports.
- Revisit RUN-only fit only if ITI dominates behavior-token occupancy and breaks locomotion tier calibration.

## Alternatives considered

- **RUN-only fit (B)** — rejected for v1.
- **Dual table, RUN fit (C)** — deferred unless `all` proves inadequate.
