---
title: Campaign Roots
type: ops
assay: nor-impress
status: na
claim_kind: na
verdict: na
tags:
  - claim/ops
  - assay/nor-impress
---
# Campaign Roots

## NOR IMPRESS

| Role                             | Path                                                                                                                                             |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Full ladder (21 models)          | `sack/datas/impress/moseq_251017/_nor_object_mi/`                                                                                                |
| Recognition-only kpMS (9 models) | `sack/datas/impress/moseq_recog_260915/anatomical/_nor_object_mi/`                                                                               |
| Per-animal paramscan             | `sack/datas/impress/nor_per_animal_paramscan/` — see [[Run Per Animal Paramscan]]; Qs: [[H Alphabet Equating]], [[V TransStruct Cross-Campaign]] |
| Behavior × physio                | `sack/crosscorr/` — see [[Run Crosscorr Spearman]]                                                                                               |
| NOR geometry H5                  | `sack/datas/impress/my_NOR_results.h5`                                                                                                           |
| Runners                          | `OpenEthoMaze/scratch/nor_object_mi/`                                                                                                            |

Wire: `session` / `trial` / `condition` — see PROTOCOL-STRATA. Boss `NOR1`… map: NOR-IMPRESS-BOSS-SESSION-MAP.

### Ladder campaign folders (Run hubs)

Under `…/moseq_251017/_nor_object_mi/`. Paths owned by Runs per [[Artifact Linking]] — do not scatter into H/F/E/V.

| Folder | Run |
|--------|-----|
| `simpler_first_object_prox_0p10/` | [[Run Object Prox DR]] |
| `simpler_first_classic_dr/` | [[Run Classic DR]] |
| `simpler_first_protocol_prologue/` | [[Run Protocol Prologue]] |
| `simpler_first_session_paired/` | [[Run Session Paired]] |
| `simpler_first_presence_steps/` | [[Run Presence Steps]] |
| `simpler_first_condition_on_paired_delta/` | [[Run Condition on Paired Delta]] |
| `simpler_first_occupancy_session_delta/` | [[Run Occupancy Session Delta]] |
| `simpler_first_bout_grammar/` | [[Run Bout Grammar]] |
| `simpler_first_side_mass/` | [[Run Side Mass]] |
| `simpler_first_quad_comp/` | [[Run QuadComp]] |
| `simpler_first_prox_comp/` | [[Run ProxComp]] |
| `simpler_first_prox_comp_per_scalar_fams/` | [[Run ProxComp Per-Scalar]] |
| `simpler_first_dr_framed_deck_exemplar/` | [[Run DR Framed Deck Exemplar]] |
| `simpler_first_prox_quad_session_delta/` | [[Run Prox Quad Session Delta]] |
| `simpler_first_prox_quad_per_model/` | [[Run Prox Quad Per Model]] |
| `simpler_first_prox_quad_comp_figs_min0/` | [[Run Prox Quad Comp Figs]] |
| `simpler_first_prox_quad_session_step_figs_min0/` | [[Run Prox Quad Session Step Figs]] |
| `simpler_first_da/` | [[Run Simpler First DA]] |
| `simpler_first_info_dr_pause/` | [[Run Info Dr Pause]] |
| `simpler_first_nearest_prox_mi__*` / `…_cluster_mi__*` | [[Run Nearest Prox MI]] (pick one) |
| `syllable_spatial_heatmaps*` | [[Run Syllable Spatial Heatmaps]] (pick one; exemplar = `…_exemplar_paramscan_s1-1e7_s2-3e4_ss-100`) |
| `simpler_first_syll_ambulation_overlap/` | [[Run Syll Ambulation Overlap]] |
| `simpler_first_syllable_kinematics/` | [[Run Syllable Kinematics]] |
| `simpler_first_syllable_signatures/` | [[Run Syllable Signatures]] |
| `slides_pack/` | [[Run Slides Pack]] |
| `simpler_first_transition_structure/` | [[Run Transition Structure]] |
| `simpler_first_transition_structure_expanded/` | [[Run Transition Structure Expanded]] |
| `simpler_first_transition_structure_full_grid/` | [[Run Transition Structure Full Grid]] |
| `simpler_first_ngram_seq/` | [[Run NGramSeq]] |
| `simpler_first_ngram_seq_expanded/` | [[Run NGramSeq Expanded]] |
| `simpler_first_ngram_seq_full_grid/` | [[Run NGramSeq Full Grid]] |
| `simpler_first_sequence_per_grain_bh/` | [[Run Sequence PerGrain BH]] |
| `simpler_first_residual_litmus/` | [[Run Residual Litmus]] |
| `simpler_first_composition_companion_audit/` | [[Run Composition Companion Audit]] |
| `simpler_first_stillness_companion_audit/` | [[Run Stillness Companion Audit]] |

### Per-animal folders

| Folder | Run |
|--------|-----|
| `nor_per_animal_paramscan/` (fits) | [[Run Per Animal Paramscan]] |
| `…/_syllable_descriptives/` | [[Run Per Animal Syllable Descriptives]] |
| `…/_nor_object_mi/simpler_first_syllable_kinematics/` | [[Run Per Animal Syllable Kinematics]] |
| `…/_nor_object_mi/simpler_first_prototype_ordination/` | [[Run Per Animal Prototype Ordination]] |
| `…/_nor_object_mi/simpler_first_prox_quad_per_animal/` | [[Run Prox Quad Per Animal]] |
| `…/_nor_object_mi/simpler_first_prox_quad_per_animal_figs/` | [[Run Prox Quad Per Animal]] (level figs) |
| `…/_nor_object_mi/simpler_first_prox_quad_per_animal_session_step_figs/` | [[Run Prox Quad Session Step Figs]] / [[Run Prox Quad Per Animal]] |

### Crosscorr folders

| Folder | Run / verdict |
|--------|---------------|
| `sack/crosscorr/out_spearman_physio_x_bh/` | [[Run Crosscorr Spearman]] · [[V DR Physio Null]] |
| `sack/crosscorr/out_spearman_engagement_delta_physio/` | [[Run Crosscorr Spearman]] · [[V Engagement Physio Null]] |

## VAST Alz (parallel assay)

| Role                            | Path                                                                                                   |
| ------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Paramscan2026 campaign          | `D:\az-sd-vast_paramscan2026\`                                                                         |
| Pose H5                         | `D:\az-sd-vast_paramscan2026\vast_results_legacy.h5`                                                   |
| Ladder arts                     | `_syllable_descriptives/`, `_syllable_bout_kinematics/`, `_syllable_signatures/`, `_da_trial_windows/` |
| Runners                         | `OpenEthoMaze/scratch/vast_moseq/` (DA primitives shared with `nor_object_mi`)                         |
| Older VAST ensemble (different) | `sack/…/AZ-SD-VAST-moseq/` — not this campaign                                                         |

Wire: `session` / trial windows / `trial_step` / `session_step`; animal strata `strain` × `tx` × `sex`. See [[VAST Alz Index]].

| Folder | Run |
|--------|-----|
| `_syllable_descriptives/` | [[Run VAST Syllable Descriptives]] |
| `_syllable_bout_kinematics/` | [[Run VAST Syllable Kinematics]] |
| `_syllable_signatures/` | [[Run VAST Syllable Signatures]] |
| `_da_trial_windows/` | [[Run VAST Trial Session Step DA]] |

## Alz NOR (pose pending — no vault folder yet)

Videos unextracted; no pose H5, no kpMS fits. When pose lands it gets its own
assay folder + index here. Do not conflate with IMPRESS NOR strata.

## Related

- [[NOR IMPRESS Index]]
- [[VAST Alz Index]]
- [[Simpler-First Ladder Pattern]]
- [[Artifact Linking]]
- [[Prune Map]]
