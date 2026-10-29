---
title: V NGramSeq Full Grid Null
type: verdict
assay: nor-impress
status: lava
claim_kind: alphabet-bound
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
  - alphabet-bound
---
# V NGramSeq Full Grid Null

**Date:** 2026-10-05  
**Scope:** [[F NGramSeq-C]] / [[Run NGramSeq Full Grid]] — all 12 NOR level grains, fixed-budget pair MI / bigram richness.  
**Gate:** 48-cell BH.  
**Status:** lava. #lava #alphabet-bound

## Verdict

**Fail.** Zero FDR hits. Min q≈0.645. Three uncorrected cells only.

## Uncorrected-only

| Cell                                           | p     | q_bh  |
| ---------------------------------------------- | ----- | ----- |
| M `bigram_richness` · `NOR_REC11hr` × `no_obj` | 0.030 | 0.645 |
| F `pair_MI` · `NOR_BL` × `no_obj`              | 0.049 | 0.645 |
| M `pair_MI` · `NOR_REC11hr` × `no_obj`         | 0.050 | 0.645 |

## Locked negative language

> Fixed-budget pair-sequence structure across the complete NOR level grid does **not** separate condition under NGramSeq-C (0/48 `hit_fdr05`). Together with TransStruct-C, bout-sequence MoSeq claims are null at every protocol level grain on this shelf.

## Figure

Honesty panel — NGramSeq-C joint. Source: [[Run NGramSeq Full Grid]].

![[fig_v_ngramseq_full_grid_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[F NGramSeq-C]] · [[Run NGramSeq Full Grid]] · [[V NGramSeq Expanded Null]] · [[V NGramSeq Null]]
- [[V TransStruct Full Grid Null]] · [[H Non-Recognition Condition Separators]]
