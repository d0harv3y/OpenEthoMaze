---
title: V NGramSeq Null
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
# V NGramSeq Null

**Date:** 2026-10-02
**Scope:** [[F NGramSeq-A]] / [[Run NGramSeq]] (declared in [[F NGramSeq-A Score Contract]] **before** peeking at q).
**Gate:** Kruskal on `pair_MI` / `bigram_richness` by `condition` within sex at `NOR_TX` × `nvl_obj` (M = 108 fixed pairs); `hit_fdr05` within the 4-cell BH family.
**Status:** lava — do not reuse without a new contract. #lava #alphabet-bound

## Verdict

**Fail.** Zero `hit_fdr05`, zero uncorrected `p < 0.05`. Best cell: F `pair_MI` (p≈0.126 → q≈0.503).

Fixed budgets worked as designed: every animal scored on exactly 108 pairs, so the TransStruct count-confound cannot apply. The null is clean, not underpowered-by-confound.

Do **not** invent Family B on these scalars without user OK.

## Evidence

| Artifact | Finding |
|----------|---------|
| `ngram_seq_tests_long.csv` | 4/4 finite p; **0** `hit_fdr05`; **0** `hit_p05` |
| `ngram_seq_per_animal.csv` | 144 rows; 144 animals (0 dropped, 0 unmapped) |
| `run_summary.json` | `pass_family_a: false` |

| Cell | p | q_bh |
|------|---|------|
| F `pair_MI` | 0.126 | 0.503 |
| M `pair_MI` | 0.524 | 0.672 |
| F `bigram_richness` | 0.385 | 0.672 |
| M `bigram_richness` | 0.672 | 0.672 |

Medians flat across arms (MI ≈ 0.15–0.17 bits; richness F ≈ 33–34, M ≈ 28).

## Cross-campaign (same scalars, exploratory — not the lock)

| Campaign | Cells | Within-model hits | Global BH |
|---|---|---|---|
| Ladder raw ×21 models | 84 | 0 | 0 |
| Recog ×9 (cluster + raw) | 72 | 0 | 0 |
| Per-animal ×9 cells (K balanced: medians 11–15 across arms) | 36 | 0 | — |

196 cells total, 0 FDR hits anywhere. Two lone uncorrected F `pair_MI` cells (ladder `s1-1e6_s2-1e4_ss-50` p≈0.046, recog `s1-1e7_s2-1e4_ss-75` p≈0.047; q≈0.19/0.14) — consistent with noise (~10 expected at α=0.05 over 192 exploratory cells), different models, no pattern. Not promoted.

Runners (exploratory cousins): see [[V NGramSeq Null]] § Cross-campaign — grid / per-animal scripts; locked A artifacts on [[Run NGramSeq]].

## Locked negative language

> Fixed-budget pair-sequence structure (adjacent-bout MI and bigram repertoire width at `NOR_TX` × `nvl_obj`) does **not** separate condition arms under NGramSeq-A (0/4 `hit_fdr05`; 0/4 uncorrected). Count-confound-free by construction.

## Figure

Honesty panel — NGramSeq-A. Source: [[Run NGramSeq]].

![[fig_v_ngramseq_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[F NGramSeq-A]] · [[E NGramSeq Pair MI]] · [[E NGramSeq Bigram Richness]] · [[Run NGramSeq]]
- Expanded grains: [[F NGramSeq-B]] · [[V NGramSeq Expanded Null]] · [[Run NGramSeq Expanded]]
- Full grid: [[F NGramSeq-C]] · [[V NGramSeq Full Grid Null]] · [[Run NGramSeq Full Grid]]
- [[E TransStruct TV Distance]] / [[E TransStruct Conditional Entropy]] — distinct 1-step scalars, also null
- [[H Non-Recognition Condition Separators]]
