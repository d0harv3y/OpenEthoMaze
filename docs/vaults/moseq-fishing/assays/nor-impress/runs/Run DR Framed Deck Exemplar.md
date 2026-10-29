---
title: Run DR Framed Deck Exemplar
type: run
assay: nor-impress
status: ladder
claim_kind: alphabet-bound
verdict: na
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - alphabet-bound
---
# Run DR Framed Deck Exemplar

**Status:** computed 2026-10-09 — join boards A/C/D + exemplar ProxComp level (E) + session-step (F) for deck spine. #ladder  
**Alphabet:** `paramscan_s1-1e7_s2-3e4_ss-100` `raw_syllable_id` (not `cluster_id`). Pause syll = **5**.  
**Eligibility:** `min_frames_n=10` (matches [[F ProxComp Per-Scalar Score Contract]]).  
**PPT FDR (deck only):** sex-stratified BH — per-scalar m=1 within `(sex, metric)`; violin boards BH within sex (role×session or role×session_step). Sealed vault contract remains m=2 F+M per scalar ([[V ProxComp Per-Scalar Null]]).

## Artifacts

**Campaign root:** `sack/.../_nor_object_mi/simpler_first_dr_framed_deck_exemplar/`

| Path | Board / role |
|------|----------------|
| `figures/fig_classic_vs_dr_time_prox_NOR_TX.*` | **A** classic DR ↔ `dr_time_prox` (on disk; not on PPT slide 1) |
| `figures/fig_frac_still_vs_syll5_share.*` | **C** `frac_still` ↔ syll5 share |
| `figures/fig_classic_vs_dr_{shannon,richness,hill2}_prox_NOR_TX.*` | **D** classic ↔ composition DR |
| `comp_level/figures/fig_exemplar_prox_{shannon,richness,hill2}_*` | **E** level/DR violins + Kruskal (sex-strat BH; min-q in footnote) |
| `session_step/figures/fig_exemplar_prox_*_session_step_*` | **F** session-step Δ boards (sex-strat BH; min-q in footnote) |
| `classic_vs_prox_assoc_NOR_TX.csv` | Spearman A/D |
| `still_vs_syll5_assoc.csv` | Spearman C |
| `comp_level/exemplar_prox_per_scalar_tests.csv` | per-scalar **sex-strat** BH @ NOR_TX |
| `comp_level/exemplar_prox_per_scalar_tests_sealed_m2.csv` | sealed-style m=2 twin |
| `scores/per_model_per_animal.csv` | exemplar rescored panel |
| `INFO_dr_framed_deck_exemplar.md` | dictionary |

**Runner:** `scratch/nor_object_mi/simpler_first_dr_framed_deck_boards.py`  
**PPT builder:** `scratch/nor_object_mi/build_dr_framed_motion_seq_deck.ps1`

## Headline associations (computed)

| Board | Pair | n | Spearman ρ | hit_p05 |
|-------|------|---|------------|---------|
| A | classic ↔ `dr_time_prox` @ NOR_TX | 139 | 0.937 | yes |
| C | `frac_still` ↔ syll5 share (ladder) | 1296 | 0.804 | yes |
| C | same @ NOR_TX × nvl_obj | 144 | 0.719 | yes |
| D | classic ↔ `dr_richness_prox` | 139 | 0.727 | yes |
| D | classic ↔ `dr_shannon_prox` | 139 | 0.079 | no |
| D | classic ↔ `dr_hill2_prox` | 139 | −0.083 | no |

## Sex-strat BH — still null (0 FDR @ 0.05)

### Per-scalar @ NOR_TX (exemplar)

| metric | sex | p | q (=p, m=1) | hit |
|--------|-----|---|-------------|-----|
| `dr_hill2_prox` | M | 0.112 | 0.112 | no |
| `dr_shannon_prox` | M | 0.181 | 0.181 | no |
| others | · | ≥0.44 | ≥0.44 | no |

### Violin boards — min q grain (footnote on PPT)

| Board | Kind | min q | Grain |
|-------|------|-------|-------|
| E (level) | shannon | 0.392 | M · nvl · NOR_TX |
| E | richness | 0.263 | M · dr · NOR_BL |
| E | hill2 | 0.322 | M · dr · NOR_BL |
| F (session-step) | shannon | 0.141 | F · nvl · REC3hr→REC11hr |
| F | richness | 0.063 | F · nvl · REC3hr→REC11hr |
| F | hill2 | 0.091 | M · nvl · BL→REC11hr |

Closest miss: F richness sex-strat q≈0.063. Joint composition bags do not create hits ([[V ProxComp Per-Scalar Null]] § exploratory).

Reuse (not rebuilt here): **B** `fig_classic_vs_object_prox`; **G** `session_paired` time twin (vault-only after PPT override).

## Related

- [[Motion Sequencing DR Framed Report]] · [[Run ProxComp Per-Scalar]] · [[Run Prox Quad Comp Figs]] · [[Run Prox Quad Session Step Figs]] · [[Run Classic DR]]
- Spatial D cousin (same alphabet model, `nvl_obj`, all sessions): [[Run Syllable Spatial Heatmaps]] → folder `syllable_spatial_heatmaps_exemplar_paramscan_s1-1e7_s2-3e4_ss-100/`
- [[V ProxComp Per-Scalar Null]] · [[H Investigation Quality]]
- [[NOR IMPRESS Index]] · [[Campaign Roots]]
