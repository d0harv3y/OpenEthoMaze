---
title: Run Slides Pack
type: run
assay: nor-impress
status: ladder
claim_kind: mixed
verdict: na
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - mixed
---
# Run Slides Pack

**Status:** human-facing composition / uncertainty / difference decks. #ladder  
**Parent:** [[H Syllable Task State]] — slides support for [[H Recognition Separators]] (**not** a recognition lock)

## Intent

Alphabet-wide Shannon / richness / Bray–Curtis / cluster frame-share / `frac_still` slide packs. Honesty: did **not** lock as consensus condition separators.

**Mixed claim kinds:** `frac_still/` (+ still↔pause story with `cluster13/`) is **#clock-portable**; Shannon / richness / BC / cluster frame-share decks are **#alphabet-bound**.

## Links

- Hypothesis: [[H Syllable Task State]]
- Honesty: [[V Engagement Delta]] · [[V Composition Companion Partial]] · [[Motion Sequencing Honest Report]]
- Upstream residual Y: [[Run Residual Litmus]] (Shannon)
- Claim kind: see [[Claim Kind]] — **mixed**

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/slides_pack/` ([[Campaign Roots]])

Each subpack: `INFO_slides_pack.md` + `figures/`. Keep/demote: [[Prune Map]] § `slides_pack/`.

| Folder | Scalar / claim | Claim kind |
|--------|----------------|------------|
| `shannon/` | Alphabet-wide Shannon (bits) | #alphabet-bound |
| `richness/` | Alphabet-wide richness | #alphabet-bound |
| `braycurtis/` | Paired step Bray–Curtis | #alphabet-bound |
| `bc_to_nosd_centroid/` | BC to noSD centroid | #alphabet-bound |
| `among_animal_beta/` | Among-animal BC PERMANOVA | #alphabet-bound |
| `cluster13/`, `cluster17/`, `cluster12/`, `cluster3/` | HDBSCAN cluster frame-share | #alphabet-bound (ids fit-local) |
| `frac_still/` | Immobile fraction (ambulation clock) | #clock-portable |
| `_grid_staging/` | Demote — grid staging | — |

### Figures (Layer A concordance highlights)

| File | Role | Claim kind |
|------|------|------------|
| `frac_still/figures/fig_frac_still_by_sex.svg` | Immobile clock by sex | #clock-portable |
| `frac_still/figures/fig_frac_still_*_step_delta_by_sex.svg` | Stillness Δ lattices | #clock-portable |
| `cluster13/figures/fig_cluster13_frame_share_by_sex.svg` | Pause-prototype share (fit-local id 13) | #alphabet-bound (id) / clock story |
| `shannon/figures/fig_shannon_level_by_sex.svg` | Shannon level protocol deck | #alphabet-bound |
| `shannon/figures/fig_shannon_*_step_delta_by_sex.svg` | Shannon Δ lattices | #alphabet-bound |

Full figure lists: each subpack `figures/FIGURES.md`.

**Rebuild:** `OpenEthoMaze/scratch/nor_object_mi/*_slides_pack.py`

## Related

- [[Prune Map]] · [[H Syllable Task State]] · [[V Engagement Delta]] · [[Claim Kind]]
- [[Run Session Paired]] · [[Run Presence Steps]] · [[Run Syllable Signatures]] · [[Run Crosscorr Spearman]]
- [[Run Syll Ambulation Overlap]] — Layer A V&V cousin
