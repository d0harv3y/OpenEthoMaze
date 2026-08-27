# ADR 0007: Stage III bout AR-HMM hyperparameters (defaults)

## Status

Accepted (2026-06-24). **`kappa` provisional** — recalibrate from bout-duration histograms before publication.

## Context

Frame kpMS uses `num_states≈100`, `nlags=5`, `stage2_kappa=1e4` at video frame rate. Bout AR-HMM steps are syllable runs (~0.5–2 s median), not 33 ms frames.

## Decision

Scratch / interim defaults for `jax_moseq.models.arhmm`:

| Parameter | Default | Notes |
|-----------|---------|-------|
| `num_states` | **20** | HDP capacity; used K often ≪ 20 |
| `nlags` | **2** | AR memory across 2–3 bouts |
| `kappa` | **50** | Bout-grain stickiness; **provisional** |
| `alpha` | **5.7** | Match `maze.kpms.fit.FitConfig` unless bout fit fails |
| `gamma` | **1e3** | Match `FitConfig` |

`latent_dim` = bout feature dimension (7 default features + duration; +optional flag columns).

Recalibration target: median **behavior-epoch** duration at bout timescale (analogous to kpMS syllable-duration FAQ), not frame κ=1e4.

## Consequences

- `fit_bout_arhmm.py` / YAML sidecar documents these defaults.
- Stage I `FitConfig` unchanged; Stage III has its own hyperparam block.

## Alternatives considered

- **B (conservative 10/20/1)** — rejected; slightly under-capacity for locomotion + still + turn splits.
- **C (YAML only, no defaults)** — rejected; need runnable scratch defaults.
