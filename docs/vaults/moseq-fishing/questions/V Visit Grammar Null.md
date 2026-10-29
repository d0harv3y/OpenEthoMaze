---
title: V Visit Grammar Null
type: verdict
assay: nor-impress
status: lava
claim_kind: clock-portable
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
  - clock-portable
aliases:
  - Q5 BoutGrammar Honesty Pass
---
# V Visit Grammar Null

**Date:** 2026-09-23  
**Scope:** [[Run Bout Grammar]] / Family BoutGrammar-A (declared in [[E Visit Grammar Counts]] **before** peeking at q).  
**Gate:** Kruskal on `n_nvl_entries` / `mean_nvl_visit_dur_s` / `frac_still_near_nvl` by `condition` within sex × 4 phases; `hit_fdr05` within the 24-cell BH family.  
**Claim kind:** #clock-portable

## Verdict

**Fail.** Zero `hit_fdr05`. Best cell: F `NOR_REC11hr` `mean_nvl_visit_dur_s` (p≈0.007 → q≈0.174). Male challenge `NOR_TX` `n_nvl_entries` is uncorrected-only (p≈0.035 → q≈0.42).

Do **not** invent Family B on the same visit scores without user OK. Recognition-linked condition separator remains unlocked (engagement Δ side claim only).

## Near miss

F `NOR_REC11hr` `mean_nvl_visit_dur_s`: p≈0.007, q≈0.174 → [[V Near Misses Watchlist]]. M TX `n_nvl_entries` (q≈0.42) is **not** a near miss.

## Locked negative language

> Portable novel-prox visit grammar (entry count, mean visit duration, still-near fraction at r = 0.10 m) does **not** separate condition arms under the pre-declared BoutGrammar-A BH family (0/24 `hit_fdr05`). This is a different design from four_mask TX−BL and from SideMass midline share — both also null on FDR.

## Evidence

Full paths + runner → [[Run Bout Grammar]].

| Artifact | Finding |
|----------|---------|
| `bout_grammar_tests_long.csv` | 24/24 finite p; **0** `hit_fdr05`; 2 `hit_p05` |
| `bout_grammar_per_animal.csv` | 431 rows; 144 animals |
| `run_summary.json` | `pass_family_a: false` |

| Top cells | p | q_bh |
|-----------|---|------|
| F REC11hr `mean_nvl_visit_dur_s` | 0.007 | **0.174** |
| M NOR_TX `n_nvl_entries` | 0.035 | 0.419 |

Medians (M TX entries): noSD ≈ 11.5, GHSD ≈ 12, RBSD ≈ 6.5 — RBSD fewer visits, not FDR-kept.

## Keep / demote

| Item | Action |
|------|--------|
| BoutGrammar-A runner + INFO | **Keep as negative** |
| Further BoutGrammar BH re-cuts | **Stop** unless new contract |
| Engagement Δ side claim | Unchanged — [[V Engagement Delta]] |

## Figure

Honesty panel — BoutGrammar-A cells (−log₁₀ p; gold = uncorrected-only, red = FDR). Source: [[Run Bout Grammar]].

![[fig_v_visit_grammar_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[E Visit Grammar Counts]]
- [[V Side Geometry Null]]
- [[V Candidate Lattice Null]]
- [[H Investigation Quality]]
- [[Run Bout Grammar]]
- [[NOR IMPRESS Index]]

#lava
