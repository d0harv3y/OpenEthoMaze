# ADR 0009: Storage layout (H5 vs cohort artifacts)

## Status

Accepted (2026-06-22, grill follow-up)

## Context

The behavioral ethogram pipeline reads pose (`kpms_tracking.h5`), ambulation (`vast_results_legacy.h5`), and kpMS apply output (`results_apply.h5`). Phase I–III add token tables, tier YAML, contrast sidecars, and review CSVs. We need a single rule for what mutates which file.

## Decision

### Read-only inputs (do not write ethogram semantics here)

| File | Role | Ethogram use |
|------|------|----------------|
| **`kpms_tracking.h5`** | Pose timeline (`tracking/anatomical`, `tracking/blob`) for kpMS preprocess | **Read only.** No syllable ids, tokens, or tiers. |
| **`vast_results_legacy.h5`** | Pipeline ambulation (`ambulation_metrics/*/xy`, `is_moving`, exploration) | **Read only** for speed/still joins. No token/tier columns. Retune ambulation → new file or versioned attrs, not in-place ethogram writes. |
| **`{stream}/seed_{NNN}/results_apply.h5`** | kpMS apply: per-recording `syllable`, `heading`, `centroid` | **Written only by kpMS apply/fit.** Do not embed cohort-level token tables (would duplicate 15×). |

### Cohort artifact root (new, on data disk)

Under kpMS project root (e.g. `test2/`):

```
behavior_ethogram/
  provenance.json              # manifest hash, git sha, phase flags, paths to source H5s
  phase_i/
    anatomical/shared/         # token clustering (from syllable_speed_cluster --scope per-stream)
    blob/shared/               # validation clustering
    fused/shared/
    contrast_sidecar.csv       # anatomical↔blob↔fused scalars per (seed, raw_id)
  phase_ii/
    locomotion_tiers.yaml
    token_tiers.csv            # token_id → tier, ambiguous flag
    calibration/               # histogram PNGs, notes
  phase_iii/
    still_behavior_labels.csv
    exemplars/                 # trial keys, grid movie paths
```

**Design docs** (glossary, ADRs, plan) stay in **git**: `scratch/kpms_ensemble_compare/`.

**Block ethogram PNGs** stay in sibling `block_ethogram_exports/` (viz only). Scripts read lookup tables from `behavior_ethogram/`; do not duplicate CSVs inside every `seed_NNN/` plot folder except projected per-seed `speed_rank_table.csv` for `--speed-reindex` (already in ADR 0003 path).

### Derived per-trial storage (later, E4 — optional)

When promoting to library (`maze/kpms/materialize.py`):

| Grain | Where | Contents |
|-------|-------|----------|
| Per frame | Trial pipeline H5 `ethogram/anatomical/` | `frame_index`, `syllable_id` (raw), optional derived `behavior_token_id`, `locomotion_tier` **as cache** with attrs pointing to `behavior_ethogram/provenance.json` |
| Per bout | Export CSV only | Bout rows with token/tier/name columns; **not** authoritative frame store |

Frame-grain **behavior** labels are always **derived**: `syllable_id` → `(seed, raw_id)` lookup → token/tier/name. Recompute when token table version changes.

### What not to put in H5

- Token clustering matrices, HDBSCAN labels for full cohort → CSV/JSON under `behavior_ethogram/`
- `locomotion_tiers.yaml` → filesystem, versioned
- Reviewer labels (`still_behavior_labels.csv`) → filesystem until merged into a published `syllable_labels.yaml` (E3)

## Consequences

- `syllable_speed_cluster.py --out-dir` should default to `behavior_ethogram/phase_i` (not `block_ethogram_exports/`).
- `block_ethogram_exports.py` takes `--behavior-root behavior_ethogram` for tier/token coloring.
- Single provenance file ties plots to a token-table version.
- `kpms_tracking.h5` and `vast_results_legacy.h5` remain stable contracts for other pipeline tools.

## Alternatives considered

- **Token tables inside each `results_apply.h5`:** 15 copies; version skew.
- **Everything in `block_ethogram_exports/`:** Mixes science tables with PNG exports; hard to audit.
- **Write tiers into `vast_results_legacy.h5`:** Violates legacy ambulation contract; conflates spot debounce with ethology.
