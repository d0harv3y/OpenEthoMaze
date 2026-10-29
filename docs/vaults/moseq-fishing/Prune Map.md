---
title: Prune Map
type: ops
assay: shared
status: lava
claim_kind: na
verdict: na
tags:
  - claim/ops
  - assay/shared
  - lava
---
# Prune Map

Opinionated demote list for `moseq_251017/_nor_object_mi/` (and notes for recog). **Demote ≠ delete:** leave on disk; stop citing in slides/story; optional move under `archive/` later.

Claim notes should cite **Run** hubs ([[Artifact Linking]]); this map stays the folder-level keep/demote inventory. Folder → Run index: [[Campaign Roots]].

## Keep — story spine

| Folder | Why |
|--------|-----|
| `simpler_first_object_prox_0p10` | [[Run Object Prox DR]] — [[H Assay Validity NOR]] [[H Novelty Preference DR]] |
| `simpler_first_classic_dr` | [[Run Classic DR]] |
| `simpler_first_protocol_prologue` | [[Run Protocol Prologue]] |
| `simpler_first_session_paired` | [[Run Session Paired]] |
| `simpler_first_presence_steps` | [[Run Presence Steps]] — object-appearance engagement |
| `simpler_first_condition_on_paired_delta` | [[Run Condition on Paired Delta]] — [[V Engagement Delta]]; [[V Recognition Lattice Null]] |
| `simpler_first_presence_steps` (condition Kruskal companion) | Replicates M `NOR_TX` `frac_near` Δ — same Run |
| `simpler_first_syll_ambulation_overlap` + `simpler_first_ambulation_clocks` | [[Run Syll Ambulation Overlap]] — Layer A V&V |
| `simpler_first_syllable_kinematics` + `simpler_first_syllable_signatures` | [[Run Syllable Kinematics]] · [[Run Syllable Signatures]] |
| `simpler_first_da` | [[Run Simpler First DA]] (cite sparingly) |
| `simpler_first_info_dr_pause` | [[Run Info Dr Pause]] |
| `simpler_first_nearest_prox_mi__paramscan_s1-1e8_s2-1e5_ss-50` **or** ensemble — pick **one** | [[Run Nearest Prox MI]] |
| `slides_pack/` — see subpack table below | [[Run Slides Pack]] — **not** a Q5 recognition lock |
| `syllable_spatial_heatmaps` **or** `…_cluster13_condition_overlay` — pick **one** campaign | [[Run Syllable Spatial Heatmaps]] (D) |
| `simpler_first_side_mass` | [[Run Side Mass]] · [[V Side Geometry Null]] |
| `simpler_first_bout_grammar` | [[Run Bout Grammar]] · [[V Visit Grammar Null]] |
| `simpler_first_occupancy_session_delta` | [[Run Occupancy Session Delta]] · [[V Occupancy Delta Null]] |
| `simpler_first_quad_comp` | [[Run QuadComp]] · [[V QuadComp Null]] — A pass / B fail |
| `simpler_first_prox_comp` | [[Run ProxComp]] · [[V ProxComp Null]] — A pass / B fail |
| `simpler_first_prox_quad_session_delta` | [[Run Prox Quad Session Delta]] — Δ×condition 0 FDR |
| `simpler_first_prox_quad_per_model` | [[Run Prox Quad Per Model]] · [[V Prox Quad Per Model Null]] — exploratory |
| `sack/crosscorr/out_spearman_physio_x_bh` (+ nested FDR tables) | [[Run Crosscorr Spearman]] · [[V DR Physio Null]] |
| `sack/crosscorr/out_spearman_engagement_delta_physio` | [[Run Crosscorr Spearman]] · [[V Engagement Physio Null]] |
| `sack/crosscorr/out_spearman_cluster13_bl_rec11` | [[Run Crosscorr Spearman]] — clean zero FDR |

### `slides_pack/` inventory (`moseq_251017/_nor_object_mi/slides_pack/`)

Each subfolder has its own `INFO_slides_pack.md` (+ figures). Rebuild scripts: see [[Run Slides Pack]].

| Subpack | Claim class | Map posture |
|---------|-------------|-------------|
| `shannon/` | Alphabet-wide Shannon (bits) — level / trial-step / session-step Kruskal | **Companion** UNCERTAINTY; consensus condition FDR miss ([[V Engagement Delta]]); OK for protocol-dynamics slides, not preference / recognition |
| `richness/` | Alphabet-wide richness — same lattices | **Companion** COUNT; same honesty landing as Shannon |
| `braycurtis/` | Paired step BC (left↔right compositions) | **Companion** DIFFERENCE; session-axis BC recovery cells were exploratory only |
| `bc_to_nosd_centroid/` | BC(animal, noSD centroid) atypicality | Exploratory level lattice; not DR |
| `among_animal_beta/` | Among-animal BC PERMANOVA by condition | Exploratory β; do not confuse with engagement Δ or recognition |
| `cluster13/` (and `cluster3`, `12`, `17`) | HDBSCAN cluster frame-share lattices | Human-facing cluster decks; **ids fit-local** (ADR-0005) — cite only clusters you still show |
| `frac_still/` | Immobile time / trial duration | Ambulation clock companion; not investigation quality |
| `_grid_staging/` | Cluster star-grid staging | **Demote** — staging / media cousin of `cluster_star_grid_movies` |

**Do not** promote Shannon / richness / BC packs to “the” condition separator after the honesty passes. Prefer engagement Δ ([[V Engagement Delta]]) for the locked non-recog side claim.

## Demote — forks / cousins / no INFO / media

| Folder | Why demote |
|--------|------------|
| `simpler_first_info_dr_pause__*` (4 forks) | Keep canonical `simpler_first_info_dr_pause` (+ maybe `…_mi_mm_nvl` if that is the MM estimator). Forks are knob variants. |
| `simpler_first_nearest_prox_cluster_mi__*` extras | Keep one locked model **or** ensemble, not both paramscan trees. |
| `simpler_first_condition_on_paired_delta_parametric` | Mean cousin of rank lattice; demote unless a figure needs it. |
| `simpler_first_da_bout_count` | Weighting variant of DA. |
| `simpler_first_occupancy_lollipop` | No `INFO_*.md`. |
| `simpler_first_occupancy_da_join` / `…_consensus` | Display/join of occupancy×DA; keep only if a slide cites them. |
| `simpler_first_four_mask` | Niche mask experiment. |
| `simpler_first_locomotor_presence` | Overlaps presence/ambulation story. |
| `simpler_first_movement_kinematics` | Unless gait claim is live. |
| `simpler_first_pause_stim_mi__*` | Stim MI — different assay question. |
| `simpler_first_info_sex_cluster` | Sex×cluster side quest. |
| `simpler_first_segmenter_pearson` | Extra V&V; keep ambulation_overlap as primary. |
| `simpler_first_nested_da` | Nested design — demote until a Q5 primary points here. |
| `cluster_star_grid_movies` | Heavy media / staging. |
| `model_syllable_locus_heatmaps` | Prefer spatial heatmap campaign. |
| Duplicate spatial: keep one of `syllable_spatial_heatmaps` / `_cluster13` / `_condition_overlay` | Three copies of the same idea. |
| `archive/` | Already demoted. |
| `sack/crosscorr/out_spearman/` (cohort) | Tiny-n \|ρ\|=1 cells — not sellable ([[V DR Physio Null]]) |
| `sack/crosscorr/out_spearman_moseq_physio` | Alphabet fishing; demote |
| `sack/crosscorr/out_spearman_tx_sex`, `out_spearman_nor_tx_psg` | Redundant with physio_x_bh |
| PERMANOVA endpoint `no_obj`×`near_0p10` as primary | Wrong trial / grain for recognition story ([[V Engagement Delta]]) |
| Raw DA syllable lists as “the” condition effect | Low density; ids not portable |
| Novelty DA @ BL/REC3 as challenge recognition | Wrong session; [[V Recognition Lattice Null]] |
| Prox MI / `info_dr_pause` as condition separators | FDR miss on audited axes |
| Absolute `frac_near_nvl` as locked separator | Declared BH Family A fails (q≈0.12) ([[V Candidate Lattice Null]]) |
| Spatial heatmaps as condition I | D-only pools |
| Side-mass Family A as locked separator | 0 FDR ([[V Side Geometry Null]]); do not re-cut without new contract |
| BoutGrammar Family A as locked separator | 0 FDR ([[V Visit Grammar Null]]); do not re-cut without new contract |
| OccSessDelta Family A as locked separator | 0 FDR ([[V Occupancy Delta Null]]); BL→TX occupancy Δ |
| four_mask / classic `t_nvl_s` as Q4 lock | FDR miss ([[V Candidate Lattice Null]]) |

## Recog campaign (`moseq_recog_260915`)

- Keep: `CAMPAIGN.md`, kinematics, signatures, spatial heatmaps, early DR/session_paired signals.
- Fill missing `INFO_*.md` on `simpler_first_object_prox_0p10` / `session_paired` before citing as primary (251017 object_prox remains DR source of truth until then).
- Empty presence ladders on nvl-only fit: demote / do not slide.

## Per-animal campaign (`nor_per_animal_paramscan`)

**Living** (scaled despite overview “litmus first” caution — bearings / TransStruct only so far):

| Path / run | Posture |
|------------|---------|
| Fits root + `CAMPAIGN.md` | Keep — [[Run Per Animal Paramscan]] |
| `_syllable_descriptives/` | Keep D QC — [[Run Per Animal Syllable Descriptives]] |
| `_nor_object_mi/simpler_first_syllable_kinematics/` | Keep ADR-0005 table — [[Run Per Animal Syllable Kinematics]] |
| `_nor_object_mi/simpler_first_prototype_ordination/` | Keep D remapping bearings — [[Run Per Animal Prototype Ordination]]; HDBSCAN knobs exploratory |
| TransStruct H/H_norm on this root | Keep as **negative** cross-campaign cell — [[V TransStruct Cross-Campaign]] |
| Prox/Quad object-stratified DR (+ Hill q=2 companion figs) | Exploratory lead — F consensus `dr_shannon_quad` / `dr_hill2_quad` FDR; not a lock — [[V Prox Quad Per Animal Exploratory]] · [[Run Prox Quad Comp Figs]] · [[Run Prox Quad Session Step Figs]] |

**Do not** sell per-animal remapping as a Q5 lock. Accent Q is infrastructure ([[H Alphabet Equating]]).

## Not yet — do not invent folders for

- Arena **quadrant** residual beyond SideMass — SideMass already **fail** ([[V Side Geometry Null]]); do not reopen without a *new* geometry definition.
- Bout grammar near nvl (duration / approach–leave) — **done / null** ([[V Visit Grammar Null]]).
- Bout **transition** structure (P(next\|current) at `NOR_TX` × `nvl_obj`) — **declared + fail** ([[Q5 Transition Structure Score Contract]] / Honesty Pass); cross-campaign also null.
- Syllable **residual litmus** — **fail** ([[F Residual-A]] / [[V Residual Litmus Null]]).
- Q4 quality score that unlocks “per-animal improves reliability” litmus — still undefined ([[H Investigation Quality]]).

## Related

- [[NOR IMPRESS Index]]
- [[Campaign Roots]]
