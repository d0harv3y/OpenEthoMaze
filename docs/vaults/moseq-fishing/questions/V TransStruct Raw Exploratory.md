---
title: V TransStruct Raw Exploratory
type: verdict
assay: nor-impress
status: snake
claim_kind: na
verdict: na
tags:
  - claim/verdict
  - assay/nor-impress
  - snake
aliases:
  - Q5 Transition Structure Raw Exploratory
---
# Q5 Transition Structure Raw Exploratory

**Date:** 2026-10-01
**Status:** exploratory — does **not** modify the locked [[V TransStruct Null]] (fail).
**Scope:** same 4 cells per model with raw `raw_syllable_id` alphabets, 21 kpMS models (84 rows).

## Finding

12 within-model `hit_fdr05`, all on `trans_dist_to_nosd_ref` in the six
`s2-1e5` models (both sexes; e.g. `paramscan_s1-1e8_s2-1e5_ss-50` M p≈0.007 →
q≈0.028). `H_next_given_curr` hits in **0/21 models**.

This is **not** a lock:

1. **Global BH over 84 cells → 0 hits** (min q≈0.066).
2. **Count confound:** TV distance correlates with bout count at r≈−0.9 within
   sex × condition (Laplace smoothing: fewer transitions → nearer-uniform P →
   farther from reference). SD arms trend fewer bouts. The count-robust H
   (|r|≈0.1) is null everywhere.
3. **Non-portable alphabet** (states differ per model) + **in-sample bias**
   (noSD animals inside their own reference).

## Locked language

> An exploratory raw-alphabet grid (21 models) reproduces no portable
> transition-structure separator: the only within-model hits are TV-distance
> cells that vanish under global FDR and ride a bout-count/smoothing
> confound, while conditional entropy is null in all models. The locked
> TransStruct-A negative stands.

## Follow-up (only with user OK + pre-declared)

A real transition test needs the confound removed first: fixed-transition
downsampling (or count-matched strata) + leave-one-out reference, one locked
alphabet, then TransStruct-A rules. Not run here.

## Figure

Locked portable-cluster TransStruct-A null (raw grid is exploratory cousin). Source: [[Run Transition Structure]].

![[fig_v_transstruct_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[Q5 Transition Structure Score Contract]] / [[V TransStruct Null]]
- [[Run Transition Structure]]

#snake
