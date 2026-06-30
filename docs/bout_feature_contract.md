# Bout scalar feature contract (Stage II / III substrate)

Schema id: **`bout_feature_v2`**. Authority: [`maze/kpms/behavior_ethogram/bout_feature_contract.py`](../maze/kpms/behavior_ethogram/bout_feature_contract.py). Implementation: [`bout_scalars.py`](../maze/kpms/behavior_ethogram/bout_scalars.py), [`compile.py`](../maze/kpms/behavior_ethogram/compile.py), [`cluster.py`](../maze/kpms/behavior_ethogram/cluster.py), [`arhmm.py`](../maze/kpms/behavior_ethogram/arhmm.py).

**Sync rule:** column and feature name tuples live in `bout_feature_contract.py`. `feature_matrix_for_clustering`, `BOUT_TABLE_FIELDS`, and `SYLLABLE_SIGNATURE_FEATURE_NAMES` must match. Contract tests: `tests/test_bout_feature_contract.py`.

Glossary for *bout* vs *Behavior*: [`maze/kpms/behavior_ethogram/CONTEXT.md`](../maze/kpms/behavior_ethogram/CONTEXT.md). Syllable signature policy: [`docs/adr/0005-syllable-kinematic-signature-not-raw-id.md`](adr/0005-syllable-kinematic-signature-not-raw-id.md).

## What is a bout row?

One **syllable bout** = a maximal run of identical kpMS `syllable` labels along **kpMS-aligned** per-frame rows (after apply preprocess / fragment filter). Each row in the bout table summarizes kinematics over that run. This is Option D substrate — not the producer-agnostic **Behavior** artifact ([`behavior_labeling_contract.md`](behavior_labeling_contract.md)).

## Artifact locations

```
<kpms_root>/behavior_ethogram/
  stage_ii/
    bout_features.csv              # compile (all seeds)
    bout_features_clustered.csv    # + cluster_id from HDBSCAN
  stage_iii/
    seed_<seed>/
      bout_behavior_tokens.csv     # + behavior_token from AR-HMM
```

Path helpers: `maze.kpms.behavior_ethogram.paths.bout_features_csv`, `bout_features_clustered_csv`, `bout_tokens_csv`.

## Per-frame inputs (compile)

All per-frame arrays share length `T` = kpMS-aligned row count for the trial. Join key to legacy / anchors: `(trial_key, source_frame_index)` via `kpms_aligned_coordinates_and_indices`.

| Source | Field used | Notes |
|--------|------------|-------|
| `results_apply.h5` | `syllable` | Bout boundaries via RLE |
| Anatomical pose | centroid, heading | `bout_kinematics.py`; anterior–posterior heading |
| Trial H5 `tracking/blob` | blob polygon area | Mapped by `source_frame_index` |
| Legacy VAST H5 | `trial_state` | Optional majority label per bout |
| Preprocess config | `px_per_cm`, `fps` | Speed in m/s |

CLI: `uv run maze-compile-bout-features --kpms-root … --manifest-path … --legacy-db …`

## CSV columns (`BOUT_TABLE_FIELDS`)

| Column | Units | Description |
|--------|-------|-------------|
| `stream` | | Pose stream (default `anatomical`). |
| `seed` | | kpMS apply seed id. |
| `trial_key` | | Recording / manifest trial key. |
| `raw_syllable_id` | | kpMS syllable id for this bout. |
| `bout_index` | | 0-based bout index within trial. |
| `row_start` | kpMS row | Inclusive start index into aligned per-frame arrays. |
| `row_end_exclusive` | kpMS row | Exclusive end index. |
| `bout_frames` | frames | `row_end_exclusive - row_start`. |
| `bout_duration_s` | s | `bout_frames / fps`. |
| `bout_mean_speed_mps` | m/s | Mean centroid speed over bout. |
| `bout_mean_abs_dheading` | rad/frame | Mean \|Δheading\| per frame (unwrapped). |
| `bout_mean_blob_area_px2` | px² | Mean blob polygon area. |
| `bout_iqr_speed_mps` | m/s | IQR of per-frame speed within bout. |
| `bout_iqr_abs_dheading` | rad/frame | IQR of per-frame \|Δheading\|. |
| `bout_iqr_blob_area_px2` | px² | IQR of per-frame blob area. |
| `bout_mean_heading_rad` | rad | Circular mean heading (CSV when `--include-heading-direction`). |
| `bout_iqr_heading_rad` | rad | Circular IQR of heading (CSV when flag set). |
| `bout_net_dheading_rad` | rad | Signed net heading change (unwrapped end − start). |
| `bout_straightness` | 0–1 | Net displacement / path length along centroid. |
| `bout_primary_state` | | Majority legacy `trial_state` in bout (e.g. `run`, `iti`). |
| `ambiguous` | 0/1 | Speed IQR above threshold (default 0.08 m/s). |
| `cluster_id` | | Stage II HDBSCAN label (QC; **not** AR-HMM input in S2). |
| `behavior_token` | | Stage III AR-HMM decoded state id. |

## ML feature sets

### Stage II clustering (`CLUSTERING_FEATURE_NAMES`, 9 columns)

Z-scored in `cluster.py` before HDBSCAN. Order matters.

1. `bout_mean_speed_mps`
2. `bout_mean_abs_dheading`
3. `bout_mean_blob_area_px2`
4. `bout_iqr_speed_mps`
5. `bout_iqr_abs_dheading`
6. `bout_iqr_blob_area_px2`
7. `bout_duration_s`
8. `bout_net_dheading_rad`
9. `bout_straightness`

### Optional heading (`OPTIONAL_HEADING_FEATURE_NAMES`, +2)

When `include_heading_direction=True` at compile / fit. Uses **sin/cos**, not raw radians (Gaussian-safe).

- `bout_mean_heading_sin`
- `bout_mean_heading_cos`

### Stage III syllable signature (`SYLLABLE_SIGNATURE_FEATURE_NAMES`, +3)

Pooled per `raw_syllable_id` over the fit cohort; appended at AR-HMM sequence build. Never raw syllable id or `cluster_id`.

- `syllable_sig_mean_speed_mps`
- `syllable_sig_mean_abs_dheading`
- `syllable_sig_mean_blob_area_px2`

### Default AR-HMM vector

`arhmm_feature_names()` = clustering (9) + optional heading (0 or 2) + signature (3) → **12** default, **14** with heading.

Rejected in S2: `include_cluster_feature`, `cluster_id` as float feature.

## Consumer rules

- Read/write CSV via `read_bout_table_csv` / `write_bout_table_csv` (`bout_table_io.py`).
- Rebuild feature matrices via `feature_matrix_for_clustering` / `feature_matrix_for_arhmm` — do not hard-code column lists elsewhere.
- After changing names or order: update `bout_feature_contract.py`, this doc, and run `pytest tests/test_bout_feature_contract.py`.
