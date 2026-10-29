---
title: V NGramSeq Expanded Null
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
# V NGramSeq Expanded Null

**Date:** 2026-10-05  
**Scope:** [[F NGramSeq-B]] / [[Run NGramSeq Expanded]]  
**Gate:** Kruskal on `pair_MI` / `bigram_richness` by `condition` within sex; `hit_fdr05` within 24-cell BH family.  
**Status:** lava. #lava #alphabet-bound

## Verdict

**Fail.** Zero `hit_fdr05`. Two uncorrected `hit_p05` only (both q≈0.50 after BH).

Expanded-grain fixed-budget n-grams do **not** separate condition — parallel null to [[V TransStruct Expanded Null]].

## Uncorrected-only

| Cell | p | q_bh |
|------|---|------|
| F `pair_MI` · `NOR_REC11hr` × `nvl_obj` | 0.029 | 0.501 |
| M `bigram_richness` · `NOR_REC11hr` × `nvl_obj` | 0.042 | 0.501 |

## Locked negative language

> Fixed-budget pair-sequence structure (adjacent-bout MI and bigram richness) at six pre-declared expanded grains (full `NOR_TX` session concat, `no_obj` / `id_obj` at challenge, baseline and recovery `nvl_obj`) does **not** separate condition arms under NGramSeq-B (0/24 `hit_fdr05`). Together with NGramSeq-A and TransStruct-A/B, bout-sequence MoSeq claims remain null for non-recognition condition separation.

## Evidence

| Artifact | Finding |
|----------|---------|
| `ngram_seq_expanded_tests_long.csv` | 24/24 finite p; **0** FDR; **2** `hit_p05` |
| `run_summary.json` | `pass_family_b: false`; per-grain M ∈ {450,129,89,87,119,64} |

Path + runner → [[Run NGramSeq Expanded]].

## Figure

Honesty panel — NGramSeq-B joint. Source: [[Run NGramSeq Expanded]].

![[fig_v_ngramseq_expanded_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[F NGramSeq-B]] · [[F NGramSeq-A]] · [[V NGramSeq Null]] · [[Run NGramSeq Expanded]]
- [[F TransStruct-B]] · [[H Non-Recognition Condition Separators]]
