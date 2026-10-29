---
title: V TransStruct Cross-Campaign
type: verdict
assay: nor-impress
status: lava
claim_kind: na
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
aliases:
  - Q5 Transition Structure Cross-Campaign Readout
---
# Q5 Transition Structure Cross-Campaign Readout

**Date:** 2026-10-01
**Status:** follow-up readout — the locked [[V TransStruct Null]] (fail) is unchanged.
**Question:** do the TransStruct scalars separate condition under other segmentations — recognition-phase pooled fits, or per-animal fits?

## Campaigns

| Campaign | Fits | Alphabet asked | TV defined? |
|---|---|---|---|
| Full ladder `moseq_251017` (locked) | 21 pooled | portable cluster | yes → **fail** 0/4 |
| Full ladder raw grid (exploratory) | 21 pooled | raw per model | yes → 12 within-model hits, 0 global; count confound |
| Recognition `moseq_recog_260915` | 9 pooled (recog-phase) | cluster + raw | yes → see below |
| Per-animal `nor_per_animal_paramscan` | 1296 (144 × 9 cells) | animal-local | **no** → H/H_norm only |

## Recognition-phase results

- Cluster: 3/36 within-model hits, all TV (`s2-1e4_ss-50` M, `s2-31622.8_ss-50` M, `s2-31622.8_ss-75` F); global BH over 36 → 0 (min q≈0.082). H: 1/36 uncorrected.
- Raw: 11/36 within-model hits, all TV; descriptive global BH → 8/36. H: 0/36 uncorrected.
- Same confound signature as the ladder: TV–count r≈−0.6…−0.99, H null.
- **Decisive check:** fixed-transition-budget downsampled rerun (seed 7, cluster alphabet) → **0/36 hits**. The TV hits were bout-count laundering, not transition structure.

## Per-animal results

- H / H_norm Kruskal by condition within sex, 9 cells × 4 = 36 tests → **0 hits, 0 even uncorrected** (best p≈0.071, min q≈0.285).
- TV never computed (incommensurable alphabets — by design, not by omission).

## Locked language

> Across three segmentation campaigns (full-ladder pooled, recognition-phase pooled, per-animal fits), no bout-transition scalar — TV distance to a noSD reference, conditional entropy, or size-adjusted entropy — survives honest error control: the only hits anywhere are TV cells that vanish under fixed transition budgets and ride a bout-count/smoothing confound, while entropy is null under FDR in all 48 model-or-cell families (21 ladder-raw + 9 recog-cluster + 9 recog-raw + 9 per-animal). Bout transition structure at recognition does not separate condition arms.

## Figure

Locked ladder TransStruct-A honesty panel (cross-campaign does not overturn this). Source: [[Run Transition Structure]].

![[fig_v_transstruct_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[Q5 Transition Structure Score Contract]] / [[V TransStruct Null]]
- [[V TransStruct Raw Exploratory]]
- [[Run Transition Structure]] / [[Run Per Animal Paramscan]] / [[Campaign Roots]] / [[NOR IMPRESS Index]]
- [[H Alphabet Equating]] (same campaign root; different claim)

#lava
