# Behavioral ethogram (kpMS + kinematics)

Domain language for turning unsupervised kpMS syllables and video-derived kinematics into interpretable behavior labels for the test2 ensemble work.

Phased goal (locked): **Phase I — stable cross-seed tokens → Phase II — locomotion tiers → Phase III — named behaviors**.

## Language

**Phase I (behavior tokens)**:
Cross-seed kinematic clustering on anatomical syllable prototypes; outputs stable token indices and scalar sidecars (including anatomical–blob contrast). No human behavior names.
_Avoid_: phase C, speed reindex

**Phase II (locomotion tiers)**:
Rule-based grouping of Phase I tokens using **anatomical** speed and heading-change scalars only (still / slow explore / fast transit / turn-heavy).
_Avoid_: phase A, grooming vs freezing split

**Phase III (named behaviors)**:
Human-validated labels attached after exemplar QC; **Phase IIIa** focuses on still-tier tokens (freeze / groom / other) using anatomical–blob contrast; **Phase IIIb** extends naming to all tokens once IIIa is stable.
_Avoid_: phase B, syllable merge without QC

**Phase IIIa (still-behavior adjudication)**:
Review 3–5 auto-picked exemplar bouts per still-tier anatomical token; assign `freeze` / `groom` / `other` / `unsure` in `still_behavior_labels.csv`, pre-sorted by cross-stream contrast.
_Avoid_: full ontology pass, merge-first naming

**Phase IIIb (full token naming)**:
Grid-movie or overlay review for every behavior token across all locomotion tiers; complete behavior ontology after Phase IIIa still pass is stable.
_Avoid_: skipping IIIa, syllable-id renaming

**Behavior token**:
A stable cross-seed kinematic phenotype index assigned after pooling **syllable prototypes** across seeds in Phase I; the unit of alignment before any human-readable name.
_Avoid_: syllable id, raw cluster_id, state number

**Syllable prototype**:
One kinematic signature per `(stream, seed, raw_syllable_id)`, built from median bout curves across trials; the object that receives a behavior token in Phase I.
_Avoid_: bout instance, frame label, syllable id (raw kpMS index)

**Bout-level diagnostic**:
Per-bout or per-cluster inequality statistics (speed range, heading DTW, occupancy spread) used to QC whether a syllable prototype is kinematically coherent before tier assignment or naming.
_Avoid_: validation set, quality metric (generic)

**Locomotion tier**:
A coarse interpretable class formed by grouping Phase I behavior tokens on anatomical speed and heading-change features (Phase II).
_Avoid_: behavior class, ethogram label (until Phase III)

**Tier assignment rule**:
The mapping from behavior token scalars to locomotion tiers. **Default:** hand-tuned thresholds in YAML (interpretable, publishable). **Target:** data-driven cut points after histogram calibration on the cohort replaces YAML defaults.
_Avoid_: speed_index bin, raw cluster_id

**Named behavior**:
A human-validated label attached to one or more behavior tokens after exemplar QC (Phase III).
_Avoid_: syllable name (kpMS merge artifact without kinematic validation)

**Kinematic signature**:
The measured movement profile of a syllable prototype: bout curves (speed + heading) for clustering, plus scalar aggregates (`mean_speed_mps`, `frac_still`, heading-change rate, occupancy) for tier rules and QC. Pose-shape features deferred to Phase III.
_Avoid_: syllable embedding, motif (visualization-only)

**Ambulation still flag**:
Legacy `is_moving` from debounced spot speed above a fixed threshold — a pipeline kinematic proxy, not a validated freeze or stop behavior. Use as a secondary scalar with provenance; prefer `mean_speed_mps` when they disagree.
_Avoid_: freezing, true stillness, immobility

**Cross-stream contrast**:
Scalars comparing anatomical vs blob kinematics on the same syllable prototype (e.g. speed delta); computed in Phase I, acted on in Phase III for still-behavior splits — not in Phase II tiers.
_Avoid_: unified token, cross-stream cluster

**Primary stream**:
The pose stream whose syllable prototypes carry authoritative behavior tokens and publication-facing ethograms (`anatomical`).
_Avoid_: default stream, main model

**Contrast stream**:
A second pose stream whose kinematic scalars are joined to the same syllable bouts for cross-stream comparison (`blob`).
_Avoid_: secondary model, backup stream

**Ambiguous token**:
A behavior token withheld from Phase II tier assignment because its syllable prototype fails bout-level coherence QC (e.g. bout speed IQR above threshold). Shown separately in exports; may be split or merged in Phase III.
_Avoid_: noise cluster, HDBSCAN outlier (-1)

**Trial phase scope**:
Phase I token tables and Phase II tier rules use **`all` trial frames** (run + ITI + other labeled states in one clustering pass). Block ethogram exports may still **display** RUN-only strata while looking up the shared token table.
_Avoid_: separate token tables per phase (deferred unless `all` proves inadequate)

**Validation stream**:
A fused pose stream used to check whether anatomical–blob contrasts replicate when both signals are combined (`fused`).
_Avoid_: ground truth, ensemble average

**Cohort artifact root**:
On-disk directory (e.g. `behavior_ethogram/` under the kpMS project root) holding Phase I–III lookup tables, YAML, and review CSVs — not inside `kpms_tracking.h5` or `vast_results_legacy.h5`.
_Avoid_: block_ethogram_exports (viz-only), results_apply.h5 (per-model raw syllables)

**Pose label**:
Task-agnostic ethological name for a behavior token (freeze, groom, walk, …) after Phase III QC.
_Avoid_: zone name, apparatus name, syllable id

**Context tag**:
Orthogonal metadata on a frame or bout — apparatus, trial epoch, zone, spatial epoch — joined from pipeline geometry; mapped per task (VAST, RAM, NOR).
_Avoid_: pose label, kpMS syllable id

**Apparatus**:
The behavioral task / arena contract (e.g. VAST circular open field, RAM radial maze, NOR).
_Avoid_: cohort, stream, session
