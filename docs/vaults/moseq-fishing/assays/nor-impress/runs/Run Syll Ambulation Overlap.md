---
title: Run Syll Ambulation Overlap
type: run
assay: nor-impress
status: ladder
claim_kind: clock-portable
verdict: na
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - clock-portable
---
# Run Syll Ambulation Overlap

**Status:** computed — Layer A V&V (syllable ∩ movement). #ladder #clock-portable  
**Parent:** [[H Syllable Task State]] / [[T4 Measurement Quality]] (instrument check, not memory)

## Intent

Syllable bout ∩ movement bout — shared boundaries / enrichment. Concordance of kpMS with classic **threshold + debounce** clocks. Not Pearson of two session clocks alone.

## Links

- Hypothesis / report: [[H Syllable Task State]] · [[Motion Sequencing Honest Report]] §1 · [[T4 Measurement Quality]]
- Claim kind: **#clock-portable** (V&V concordance — MoSeq reproduces the classic clock)
- Cousin: [[Run Syllable Kinematics]] · [[Run Slides Pack]] (`frac_still/`, `cluster13/`)

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_syll_ambulation_overlap/` ([[Campaign Roots]])

| File | Role |
|------|------|
| overlap / enrichment tables | D / V&V |
| `INFO_syll_ambulation_overlap.md` | Data dictionary |

**Companion clock folder:** `…/simpler_first_ambulation_clocks/` (Layer A duration / n_bouts / association)

### Figures

| File | Role | Claim kind |
|------|------|------------|
| `fig_syll_locomotor_duration_slides.svg` | Bout-duration concordance slides | #clock-portable |
| `fig_syll_locomotor_identity_slides.svg` | Identity / labeling concordance | #clock-portable |
| `fig_syll_locomotor_mi_slides.svg` | Shared-info / MI concordance | #clock-portable |
| `../simpler_first_ambulation_clocks/figures/fig_clock_association.png` | Clock association | #clock-portable |
| `../simpler_first_ambulation_clocks/figures/fig_clock_duration.png` | Clock duration | #clock-portable |
| `../simpler_first_ambulation_clocks/figures/fig_clock_n_bouts.png` | Bout-count clock | #clock-portable |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/` — ambulation-overlap suite

## Related

- [[Run Syllable Kinematics]] · [[Prune Map]] · [[Claim Kind]]
