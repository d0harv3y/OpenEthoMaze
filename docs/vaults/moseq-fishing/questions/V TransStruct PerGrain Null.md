---
title: V TransStruct PerGrain Null
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
# V TransStruct PerGrain Null

**Date:** 2026-10-05  
**Scope:** [[F TransStruct-PerGrain]] / [[Run Sequence PerGrain BH]] — BH within each of 12 level grains (m=4).  
**Claim kind:** #alphabet-bound #lava  
**Distinct from:** joint [[V TransStruct Full Grid Null]] (m=48) and [[V TransStruct Expanded Null]] (m=24).

## Verdict

**Fail under the commensurate bar.** Zero grains pass; zero cell `hit_fdr05` when each grain gets the same m=4 BH as [[F TransStruct-A]].

Joint-panel hardness was **not** what was hiding a lock. Closest cell: F `H_next_given_curr` @ `NOR_REC11hr` × `no_obj` (p≈0.018 → per-grain q≈0.050) — still miss.

## Locked negative language

> Bout-transition structure (portable cluster TV-to-noSD and H(next|current)) does **not** separate condition at any NOR level grain under per-grain TransStruct families commensurate with TransStruct-A (m=4 within each `session × trial`; 0/12 grains pass; 0 cell-level `hit_fdr05`).

## Figure

Honesty panel — TransStruct-PerGrain (m=4 within each grain). Source: [[Run Sequence PerGrain BH]].

![[fig_v_transstruct_pergrain_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[F TransStruct-PerGrain]] · [[Joint vs Per-Grain FDR]] · [[V TransStruct Full Grid Null]] · [[V TransStruct Null]]
- [[H Non-Recognition Condition Separators]] · [[F NGramSeq-PerGrain]]
