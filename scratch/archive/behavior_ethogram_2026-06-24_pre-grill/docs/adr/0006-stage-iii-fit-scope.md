# ADR 0006: Stage III fit scope (single model vs multi-seed interim)

## Status

Accepted (2026-06-24)

## Context

The test2 cohort has multiple anatomical kpMS seeds from an ensemble sweep. The lab is still collecting; the target is one kpMS fit and one ethogram model on the full dataset — not ongoing multi-seed comparison.

## Decision

### Steady state (default path)

- **One** anatomical kpMS checkpoint → **one** Stage III bout AR-HMM on all trials.
- CLI and artifact layout assume `fit_scope=single` (no seed dimension in behavior-token tables).
- Multi-seed ensemble work stays archived / out of the ethogram default path.

### Interim (multiple seeds on disk today)

While legacy multi-seed `results_apply.h5` trees exist:

| Mode | Flag | Use |
|------|------|-----|
| **Per-seed AR-HMM** (interim default) | default | One bout AR-HMM per `anatomical/seed_*`; behavior state ids not aligned across seeds |
| **Pooled cohort AR-HMM** (experiment) | `--pooled-cohort` | Single AR-HMM batch over all seeds' trials; shared behavior token ids |

User may try `--pooled-cohort` first out of interest; interim default remains per-seed until the cohort migrates to a single kpMS model.

### Stage II HDBSCAN

Cohort HDBSCAN on bout rows may still pool all interim seeds for `cluster_id` (QC); independent of Stage III fit scope choice.

## Consequences

- `fit_bout_arhmm.py`: `--pooled-cohort` default false; document single-model as target when only one `results_apply.h5` exists.
- Artifact paths: `behavior_ethogram/stage_iii/` for single model; `behavior_ethogram/stage_iii/seed_{NNN}/` interim per-seed only when multiple checkpoints present.

## Alternatives considered

- **Pooled default** — rejected for interim; per-seed respects different Gibbs paths until one model replaces all seeds.
- **Always per-seed forever** — rejected; contradicts single full-dataset fit goal.
