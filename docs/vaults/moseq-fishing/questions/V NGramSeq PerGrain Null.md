---
title: V NGramSeq PerGrain Null
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
# V NGramSeq PerGrain Null

**Date:** 2026-10-05  
**Scope:** [[F NGramSeq-PerGrain]] / [[Run Sequence PerGrain BH]] — BH within each of 12 level grains (m=4).  
**Claim kind:** #alphabet-bound #lava  
**Distinct from:** joint [[V NGramSeq Full Grid Null]] / [[V NGramSeq Expanded Null]].

## Verdict

**Fail under the commensurate bar.** Zero grains pass; zero cell `hit_fdr05` at per-grain m=4 (same bar as [[F NGramSeq-A]]).

## Locked negative language

> Fixed-budget pair-sequence structure (pair MI / bigram richness) does **not** separate condition at any NOR level grain under per-grain NGramSeq families commensurate with NGramSeq-A (m=4 within each grain; 0/12 grains pass; 0 cell-level `hit_fdr05`).

## Figure

Honesty panel — NGramSeq-PerGrain. Source: [[Run Sequence PerGrain BH]].

![[fig_v_ngramseq_pergrain_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[F NGramSeq-PerGrain]] · [[Joint vs Per-Grain FDR]] · [[V NGramSeq Full Grid Null]] · [[V NGramSeq Null]]
- [[V TransStruct PerGrain Null]] · [[H Non-Recognition Condition Separators]]
