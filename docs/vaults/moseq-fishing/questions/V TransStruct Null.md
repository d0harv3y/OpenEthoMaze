---
title: V TransStruct Null
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
aliases:
  - Q5 Transition Structure Honesty Pass
---
# Q5 Transition Structure Honesty Pass

**Date:** 2026-10-01
**Scope:** [[Run Transition Structure]] / [[F TransStruct-A]] (declared in [[Q5 Transition Structure Score Contract]] **before** peeking at q; contract stub → E/F notes).
**Gate:** Kruskal on `trans_dist_to_nosd_ref` / `H_next_given_curr` by `condition` within sex at `NOR_TX` × `nvl_obj`; `hit_fdr05` within the 4-cell BH family.  
**Claim kind:** #alphabet-bound

## Verdict

**Fail.** Zero `hit_fdr05` — and zero uncorrected `p < 0.05` either. Best cell: M `H_next_given_curr` (p≈0.078 → q≈0.312).

Do **not** invent Family B (full-session `NOR_TX`, BL→TX Δ, recovery sessions, edge fishing) on these scalars without user OK. Recognition-linked condition separator remains unlocked (engagement Δ side claim only).

## Near miss

None. Best uncorrected p≈0.078 does not meet the `p < 0.05` watch-list bar → no [[V Near Misses Watchlist]] entry.

## Locked negative language

> Portable bout-transition structure (cluster_id P(next | current) total-variation distance to the sex-pooled noSD reference, plus H(next | current), at `NOR_TX` × `nvl_obj`) does **not** separate condition arms under the pre-declared TransStruct-A BH family (0/4 `hit_fdr05`; 0/4 uncorrected `p < 0.05`). This is a different design from composition (Shannon / BC / DA), engagement Δ, SideMass geometry, BoutGrammar visit counts/durations, and BL→TX occupancy Δ — all also null on FDR.

## Evidence

| Artifact | Finding |
|----------|---------|
| `transition_structure_tests_long.csv` | 4/4 finite p; **0** `hit_fdr05`; **0** `hit_p05` |
| `transition_structure_per_animal.csv` | 144 rows; 144 animals (24 per sex × condition; 0 dropped, 0 unmapped) |
| `run_summary.json` | `pass_family_a: false` |

Full paths + runner → [[Run Transition Structure]]. Cell table / INFO stay on disk.

| Cell | p | q_bh |
|------|---|------|
| F `trans_dist_to_nosd_ref` | 0.334 | 0.410 |
| M `trans_dist_to_nosd_ref` | 0.168 | 0.337 |
| F `H_next_given_curr` | 0.410 | 0.410 |
| M `H_next_given_curr` | 0.078 | 0.312 |

Medians (M TV distance): noSD ≈ 6.92, GHSD ≈ 7.11, RBSD ≈ 7.19 — no arm separation. Medians (M H bits): noSD ≈ 3.31, GHSD ≈ 3.35, RBSD ≈ 3.39.

Design notes: 21 portable `cluster_id` states (pilot `paramscan_s1-1e8_s2-1e5_ss-50` raw, Laplace α=1.0, TV on full flattened P). Bout stream is RLE so consecutive bouts differ by construction (raw diagonal counts zero); min 109 bouts/animal, references F 5993 / M 5359 pooled noSD transitions.

## Keep / demote

| Item | Action |
|------|--------|
| TransStruct-A runner + INFO | **Keep as negative** |
| Further TransStruct BH re-cuts / Family B | **Stop** unless new contract + user OK |
| Engagement Δ side claim | Unchanged — [[V Engagement Delta]] |

## Figure

Honesty panel — TransStruct-A (m=4). Source: [[Run Transition Structure]].

![[fig_v_transstruct_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[Q5 Transition Structure Score Contract]]
- [[V Visit Grammar Null]] — different claim (visit grammar), also null
- [[V Occupancy Delta Null]]
- [[V Side Geometry Null]]
- [[V Candidate Lattice Null]]
- [[H Investigation Quality]]
- [[Run Transition Structure]]
- [[NOR IMPRESS Index]]

#lava
