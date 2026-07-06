# Behavior token review contract (Option D / Stage III)

Glossary: [`maze/kpms/behavior_ethogram/CONTEXT.md`](../maze/kpms/behavior_ethogram/CONTEXT.md) (**Behavior token**, **Behavior token labels**, **anchor_bucket**). Bout substrate: [`bout_feature_contract.md`](bout_feature_contract.md). S0 export: [`behavior_labeling_contract.md`](behavior_labeling_contract.md).

> **Grill decisions (2026-07-06):** token-grain exploration, ethology-grain publish; per-seed fit; fit-scoped labels; grid overlay review; phased occupancy → session trends → transitions. See [§ Curation workflow](#curation-workflow).

## Goals

1. **Name tokens** — map fit-local `behavior_token` ids to portable ethological `behavior_name`s (`groom`, `rear`, …) using grid exemplars.
2. **Strata occupancy** — compare token or ethology occupancy across `(session, tx, sex, strain)`.
3. **Temporal change** — compare occupancy and bout transitions across sessions (and optionally trial blocks).

**Analysis unit:** explore and QC at **token grain**; publish strata stats at **ethology grain** after `behavior_token_labels.csv` is complete (unless `--allow-partial`).

## Workflow (fit → grid → label → summarize → export)

1. **Compile** bout features → `stage_ii/bout_features.csv`
2. **Cluster** (optional QC) → `bout_features_clustered.csv`
3. **Fit AR-HMM** per seed → `stage_iii/seed_<seed>/bout_behavior_tokens.csv` + `bout_arhmm_fit_summary.json`
4. **Calibrate locomotion tiers** (auto) → `locomotion_tiers.yaml`, `token_tiers.csv` — kinetic reference only, not ethology
5. **Init labels** → scaffold `behavior_token_labels.csv` (one row per token with bout count ≥ threshold)
6. **Grid review** → one grid MP4 per token; stamp `reviewed_at` / `reviewed_trial_key`; fill `behavior_name`, `anchor_bucket`
7. **Summarize** (phased) → occupancy CSV → session-stratified occupancy → transition CSV
8. **Export** S0 → `producers/bout_arhmm/seed_<seed>/` (ethology names from labels file)

Rules are **per-seed fit** (raw `behavior_token` ids are fit-local). Only **`behavior_name` strings** are portable across seeds/refits.

**Refit policy:** labels are **fit-scoped**. After `maze-fit-bout-arhmm` changes, `behavior_token_labels.csv` is stale — re-run grids and re-curate. Provenance ties to `bout_arhmm_fit_summary.json` (centroid carry-forward is a future nice-to-have, not v1).

## Artifact locations

```
<kpms_root>/behavior_ethogram/
  stage_iii/seed_<seed>/
    bout_behavior_tokens.csv       # AR-HMM decode (+ bout scalars)
    bout_arhmm_fit_summary.json    # fit provenance (labels must match)
    locomotion_tiers.yaml          # auto kinetic tiers
    token_tiers.csv                # bout-level tier assignment
    behavior_token_labels.csv      # human ethology map (this contract)
    grid_movies/
      token_07.mp4                 # exemplar grid per token
    summaries/
      occupancy.csv                # phased deliverable 1
      occupancy_by_session.csv     # phased deliverable 2
      transitions.csv              # phased deliverable 3

  producers/bout_arhmm/seed_<seed>/
    behavior_frames.h5
    behavior_bouts.csv
    provenance.json
```

Path helpers (existing): `stage_iii_dir`, `bout_tokens_csv`, `arhmm_fit_summary_json`, `token_tiers_csv`, `behavior_token_labels_csv`, `token_grid_movies_dir`, `producer_dir`. **Planned:** `token_summaries_dir`.

## `behavior_token_labels.csv`

One row per unique `behavior_token` for the fit. Many tokens may share one `behavior_name`.

| Column | Description |
|--------|-------------|
| `behavior_token` | Fit-local AR-HMM state id (integer) |
| `token_n_bouts` | Bout count for this token (reference; from centroids) |
| `token_mean_speed_mps` | Pooled centroid speed (reference) |
| `token_mean_abs_dheading` | Pooled centroid heading change (reference) |
| `locomotion_tier` | Auto tier from `calibrate-locomotion-tiers` (reference only) |
| `behavior_name` | Curator-assigned portable ethology name (empty until curated) |
| `anchor_bucket` | `moving` \| `still` \| `ignore` — harness tag |
| `reviewed_at` | ISO timestamp after grid review |
| `reviewed_trial_key` | Trial key of watched exemplar bout |
| `notes` | Optional |

### Review gates

| Grain | Gate |
|-------|------|
| **Token** | Always allowed after AR-HMM fit |
| **Ethology** | Every token with `token_n_bouts ≥ --min-token-bouts` (default 20) must have `behavior_name` + `reviewed_at`, unless `--allow-partial` |
| **S0 export** | Same as ethology grain |

## Token grid movies

Each grid is **one MP4 per `behavior_token`**, analogous to kpMS syllable grid movies but at **bout grain**.

| Property | Value |
|----------|-------|
| Cell | One bout instance assigned that token |
| Span | Bout `source_frame` bounds ± **1 s** padding (default; same as grammar preview) |
| Overlay | **Unified overlay** when video exists (pose + syllable ethogram strip + token id label) |
| Fallback | **Keypoints-only** tiles when video path missing (`--keypoints-only`) |
| Sampling | ~8–12 diverse bouts per token; spread trials; prefer non-`ambiguous`; speeds near token centroid |

Grid review is **required** for ethological naming (pose-shaped classes like groom vs rear cannot be resolved from scalars alone).

## Summarize outputs (phased)

All tables include a `phase` column: `run` \| `iti`. CLI defaults to `--phase run`; `--phase all` emits both.

**Strata keys:** `(session, tx, sex, strain)` from manifest / treatment labels (same join as `block-ethogram-exports`).

### Phase 1 — `occupancy.csv`

Fraction of phase time (or bout count) per token or ethology per stratum.

| Column | Description |
|--------|-------------|
| `grain` | `token` \| `ethology` |
| `label` | `behavior_token` int or `behavior_name` string |
| `phase` | `run` \| `iti` |
| `session`, `tx`, `sex`, `strain` | Strata |
| `occupancy_fraction` | Label time / phase time in stratum |
| `n_trials`, `n_animals` | Coverage |

### Phase 2 — `occupancy_by_session.csv`

Same as phase 1 with **session** as the time axis (goal 3: change over sessions).

### Phase 3 — `transitions.csv`

Consecutive bout `label_i → label_j` counts or rates per stratum (and optionally per session).

## Curation workflow

Grill decisions (2026-07-06):

| # | Decision |
|---|----------|
| Q1 | Three goals: name tokens, strata occupancy, temporal change |
| Q2 | Analysis unit D: token grain explore, ethology grain publish |
| Q3 | `behavior_token_labels.csv` canonical per-token map |
| Q4 | Grid cells: unified overlay + keypoints-only fallback; bout ± 1 s |
| Q5 | Summarize phased: occupancy → session trends → transitions |
| Q6 | `phase` column (`run` / `iti`); default `run` |
| Q7 | Token stats always; ethology stats gated (`--allow-partial` for drafts) |
| Q8 | Per-seed fit; portable `behavior_name` strings across seeds |
| Q9 | Fit-scoped labels; refit = re-curate |

**Operational loop:**

1. `maze-fit-bout-arhmm --kpms-root … --seed …`
2. `maze-calibrate-locomotion-tiers --kpms-root …` (reference tiers)
3. `maze-init-behavior-token-labels --kpms-root … --seed …` *(shipped)*
4. `maze-preview-behavior-token-grid --kpms-root … --seed … --manifest-path … --pipeline-h5 …` *(shipped)*
5. Fill `behavior_name`, `anchor_bucket`; stamp `reviewed_at`
6. `maze-summarize-behavior-tokens --kpms-root … --seed … --grain token` then `--grain ethology` *(planned)*
7. `maze-export-bout-arhmm-labeling --kpms-root … --seed …` (reads labels file when present)

## CLIs

**Existing:**

```bash
uv run maze-compile-bout-features --kpms-root … --manifest-path … --legacy-db …
uv run maze-cluster-bouts-hdbscan --kpms-root …
uv run maze-fit-bout-arhmm --kpms-root … --seed …
uv run maze-calibrate-locomotion-tiers --kpms-root …
uv run maze-export-bout-arhmm-labeling --kpms-root … --seed … --manifest-path …
uv run maze-block-ethogram-exports --kpms-root … --legacy-db … --manifest-path …  # tier strips only
```

**Planned (this contract):**

```bash
uv run maze-init-behavior-token-labels --kpms-root … --seed …
uv run maze-summarize-behavior-tokens --kpms-root … --seed … --grain {token,ethology} --phase {run,iti,all}
```

**Shipped:**

```bash
uv run maze-preview-behavior-token-grid --kpms-root … --seed … --manifest-path … --pipeline-h5 … [--token 3,7] [--keypoints-only]
```

## Implementation status

| Piece | Status |
|-------|--------|
| AR-HMM fit + bout CSV | Shipped |
| Locomotion tiers | Shipped |
| `behavior_token_labels.csv` init CLI | **Shipped** — `maze-init-behavior-token-labels` |
| Token grid movies | **Shipped** — `maze-preview-behavior-token-grid` |
| Summarize (occupancy / session / transitions) | **Not implemented** |
| Export reads labels file | **Not implemented** (`token_{id}` placeholder today) |
