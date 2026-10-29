---
title: V Residual Litmus Null
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
# V Residual Litmus Null

**Date:** 2026-10-05  
**Scope:** [[Run Residual Litmus]] / Family [[F Residual-A]] (declared **before** peeking at q).  
**Gate:** Kruskal on `resid_shannon_bits` / `resid_H_next_given_curr` / `resid_pair_MI` by `condition` within sex at `NOR_TX` × `nvl_obj`; `hit_fdr05` within the 6-cell BH family.  
**Status:** lava — do not reuse without a new contract. #lava #alphabet-bound

## Verdict

**Fail.** Zero `hit_fdr05` — and zero uncorrected `p < 0.05` on residuals. Best residual cell: F `resid_pair_MI` (p≈0.118 → q≈0.578).

Syllable leftovers after Layer A regression do **not** separate condition arms. Combined with raw-sequence nulls ([[V TransStruct Null]], [[V NGramSeq Null]]), MoSeq scores on this shelf are **redundant for the condition story** once speed / immobile / `frac_near` are accounted for.

Do **not** invent Family B (DR Spearman companion as primary, more `Y`, full-session, recovery) without user OK.

## Near miss

None on residuals (no `p < 0.05`).

**Descriptive collinearity note (not Family A):** raw companion Kruskal shows M `shannon_bits` uncorrected p≈0.041 → q≈0.234 (not FDR); after residualization that cell becomes p≈0.971. That is the litmus working as designed — composition track of the engagement / movement clock.

## Locked negative language

> After OLS residualizing Shannon bits, H(next | current), and fixed-budget pair MI on mean speed, immobile share (`frac_still`), and `frac_near_nvl` within sex at `NOR_TX` × `nvl_obj`, residuals do **not** separate condition arms under the pre-declared Residual-A BH family (0/6 `hit_fdr05`; 0/6 uncorrected `p < 0.05`). Syllable scalars on this shelf are redundant for condition separation beyond the Layer A locomotor / proximity clock.

## Evidence

| Artifact | Finding |
|----------|---------|
| `residual_litmus_tests_long.csv` | 6/6 finite p; **0** `hit_fdr05`; **0** `hit_p05` |
| `residual_litmus_per_animal.csv` | 144 animals; 0 dropped incomplete |
| `run_summary.json` | `pass_family_a: false` |
| `INFO_residual_litmus.md` | data dictionary |

| Cell | p | q_bh |
|------|---|------|
| F `resid_shannon_bits` | 0.473 | 0.650 |
| M `resid_shannon_bits` | 0.971 | 0.971 |
| F `resid_H_next_given_curr` | 0.254 | 0.578 |
| M `resid_H_next_given_curr` | 0.542 | 0.650 |
| F `resid_pair_MI` | 0.118 | 0.578 |
| M `resid_pair_MI` | 0.289 | 0.578 |

Path + runner → [[Run Residual Litmus]].

## Keep / demote

| Item | Action |
|------|--------|
| Residual-A runner + INFO | **Keep as negative** |
| Further residual BH re-cuts / Family B | **Stop** unless new contract + user OK |
| Engagement Δ side claim | Unchanged — [[V Engagement Delta]] |

## Figure

Honesty panel — Residual-A. Source: [[Run Residual Litmus]].

![[fig_v_residual_litmus_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[F Residual-A]] · [[E Residual Shannon]] · [[E Residual Cond Entropy]] · [[E Residual Pair MI]]
- [[Run Residual Litmus]]
- [[V TransStruct Null]] · [[V NGramSeq Null]]
- [[Motion Sequencing Honest Report]]
- [[H Non-Recognition Condition Separators]] · [[NOR IMPRESS Index]]
