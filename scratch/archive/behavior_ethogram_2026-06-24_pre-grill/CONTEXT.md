# Behavioral ethogram (anatomical, three-stage)

Ubiquitous language for turning anatomical kpMS syllables and per-frame kinematics into interpretable behavior labels. **Anatomical stream only** for kpMS fit and ethogram analysis.

Phased goal: **Stage I syllables → Stage II bout table + clusters → Stage III behavior tokens + locomotion tiers**. Human pose naming (Phase III) **deferred** until single-model cohort fit stabilizes.

## Language

**Stage I (frame syllables)**:
Per-frame discrete states from anatomical kpMS fit/apply (`results_apply.h5`). Syllable ids are seed-specific pose motifs, not behavior names.
_Avoid_: behavior token, ethogram label, bout cluster

**Stage II (bout table + cluster)**:
Syllable runs collapsed to **bout instances**; each bout gets scalar kinematics (speed, heading, blob area, within-bout IQRs, duration) plus an HDBSCAN **bout cluster** id pooled across seeds. Clusters group similar bout kinematics for QC and cross-seed comparison — not the final ethogram state.
_Avoid_: syllable prototype, padded curve features, behavior token

**Stage III (bout behavior epochs)**:
Sticky HDP **AR-HMM** (same inference family as kpMS / `jax_moseq`) fit on bout-sequence feature trajectories per trial. Hidden state at each bout step is the **behavior token** candidate before human naming.
_Avoid_: prototype clustering, frame-level HMM refit, plain EM Gaussian HMM (prototype)

**Bout instance**:
One contiguous run of the same raw syllable id within a trial (after kpMS row alignment). The row in the bout feature table.
_Avoid_: syllable prototype, frame, behavior token

**Bout feature vector**:
Per-bout scalars: mean speed, mean absolute Δheading (turning rate), mean blob area; IQR of each within the bout; bout duration (frames or seconds). Optionally circular mean heading + IQR when `include_heading_direction=true`. No resampled pose curves or padded `T_max` vectors.
_Avoid_: kinematic signature (old curve sense), feat_000…feat_N, prototype embedding

**Bout cluster**:
HDBSCAN label on z-scored bout feature vectors, fit on the cohort (all seeds' bouts). Stored as `cluster_id` on each bout row. Used for **QC and visualization** by default; optionally included in Stage III AR-HMM inputs when `include_cluster_feature=true`. May be `-1` (noise).
_Avoid_: behavior token, syllable id, locomotion tier

**Behavior token**:
Discrete hidden state from Stage III bout AR-HMM (one label per bout after decode). Stable within a fitted model; aligned across seeds only after explicit state-matching — not raw syllable id.
_Avoid_: raw syllable id, bout cluster id, cluster_id alone

**Blob area (bout scalar)**:
Mean and IQR of backup-tracker polygon area (px²) within the bout, from `tracking/blob` on the trial H5 — a kinematic scalar, not a separate kpMS stream.
_Avoid_: blob stream, fused stream, contrast stream

**Locomotion tier**:
Coarse interpretable class from rule-based grouping of behavior-token centroids (post–Stage III), analogous to prior Phase II.
_Avoid_: bout cluster, syllable speed index

**Named behavior**:
A human-validated label attached to one or more behavior tokens after exemplar QC. **Deferred** (ADR 0009) — not in the first implementation slice.
_Avoid_: syllable name, bout cluster name

**Cohort artifact root**:
On-disk `behavior_ethogram/` under the kpMS project root — bout tables, cluster sidecars, AR-HMM checkpoints, tier YAML, review CSVs. Not inside per-model `results_apply.h5`.
_Avoid_: block_ethogram_exports (viz-only)

**Trial phase scope**:
Bout tables and AR-HMM use **`all`** trial frames unless a later ADR splits RUN vs ITI. Exports may stratify display only.
_Avoid_: separate models per phase (default)

**Ambiguous bout**:
A bout flagged when within-bout IQR on speed (or combined kinematic spread) exceeds a threshold — mixture / QC, not an HDBSCAN outlier per se.
_Avoid_: ambiguous token (old prototype sense)

**Single-model path**:
The production workflow: one anatomical kpMS checkpoint and one Stage III bout AR-HMM fit on the full cohort. No multi-seed ensemble or per-seed token tables in the default ethogram pipeline.
_Avoid_: ensemble compare, seed sweep (as default workflow)

**Interim multi-seed fit**:
While the cohort still has multiple kpMS seeds on disk, Stage III may be run per-seed (default) or pooled across seeds (`--pooled-cohort`) for experiments. Interim only — not the long-term default.
_Avoid_: primary workflow, publication path
