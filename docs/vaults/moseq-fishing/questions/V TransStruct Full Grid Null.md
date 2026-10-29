---
title: V TransStruct Full Grid Null
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
# V TransStruct Full Grid Null

**Date:** 2026-10-05  
**Scope:** [[F TransStruct-C]] / [[Run Transition Structure Full Grid]] — all 12 NOR `session × trial` level grains.  
**Gate:** 48-cell BH; `hit_fdr05` ⇔ `q_bh < 0.05`.  
**Status:** lava. #lava #alphabet-bound

## Verdict

**Fail.** Zero FDR hits. Min q≈0.295. Seven uncorrected cells cluster in recovery / `no_obj`–heavy grains — none survive multiplicity.

## Uncorrected-only (descriptive)

| Cell | p | q_bh |
|------|---|------|
| M TV · `NOR_REC3hr` × `no_obj` | 0.014 | 0.295 |
| F H · `NOR_REC11hr` × `no_obj` | 0.018 | 0.295 |
| M TV · `NOR_REC3hr` × `id_obj` | 0.019 | 0.295 |
| F TV · `NOR_REC11hr` × `no_obj` | 0.025 | 0.295 |
| M TV · `NOR_REC3hr` × `nvl_obj` | 0.037 | 0.295 |
| F TV · `NOR_REC11hr` × `id_obj` | 0.037 | 0.295 |
| M H · `NOR_TX` × `id_obj` | 0.046 | 0.312 |

## Locked negative language

> Bout-transition structure (portable cluster TV-to-noSD reference and H(next|current)) across the **complete** NOR level grid (4 sessions × 3 trials) does **not** separate condition arms under TransStruct-C (0/48 `hit_fdr05`). Level-grain coverage for transition claims is saturated for this cohort and alphabet.

## Figure

Honesty panel — TransStruct-C joint (m=48). Source: [[Run Transition Structure Full Grid]].

![[fig_v_transstruct_full_grid_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[F TransStruct-C]] · [[Run Transition Structure Full Grid]] · [[V TransStruct Expanded Null]] · [[V TransStruct Null]]
- [[H Non-Recognition Condition Separators]] · [[V NGramSeq Full Grid Null]]
