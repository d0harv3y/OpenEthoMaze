---
title: V TransStruct Expanded Null
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
# V TransStruct Expanded Null

**Date:** 2026-10-05  
**Scope:** [[F TransStruct-B]] / [[Run Transition Structure Expanded]]  
**Gate:** Kruskal on TV + H(next|current) by `condition` within sex; `hit_fdr05` within 24-cell BH family.  
**Claim kind:** #alphabet-bound #lava

## Verdict

**Fail.** Zero `hit_fdr05`. Two uncorrected `hit_p05` only (not near-miss bar for watch list if q high).

Do **not** merge with raw-alphabet exploratory TV hits or invent Family C without user OK.

## Uncorrected-only (descriptive)

| Cell | p | q_bh |
|------|---|------|
| M `trans_dist_to_nosd_ref` · `NOR_REC3hr` × `nvl_obj` | 0.037 | 0.352 |
| M `H_next_given_curr` · `NOR_TX` × `id_obj` | 0.046 | 0.352 |

**0** pass `q_bh < 0.05` under 24-cell BH.

## Locked negative language

> Expanded-grain bout-transition structure (portable `cluster_id` P(next|current) TV to sex-pooled noSD reference plus H(next|current) at six pre-declared session×trial grains including full `NOR_TX` session concat) does **not** separate condition arms under TransStruct-B (0/24 `hit_fdr05`). Recognition-linked and challenge-wide transition claims remain null alongside TransStruct-A.

## Evidence

| Artifact | Finding |
|----------|---------|
| `transition_structure_expanded_tests_long.csv` | 24/24 finite p; **0** `hit_fdr05`; **2** `hit_p05` |
| `run_summary.json` | `pass_family_b: false` |
| `INFO_transition_structure_expanded.md` | data dictionary |

Path + runner → [[Run Transition Structure Expanded]].

## Figure

Honesty panel — TransStruct-B joint (m=24). Source: [[Run Transition Structure Expanded]].

![[fig_v_transstruct_expanded_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[H Non-Recognition Condition Separators]] · [[F TransStruct-B]] · [[F TransStruct-A]] · [[V TransStruct Null]]
- [[Run Transition Structure Expanded]] · [[Motion Sequencing Honest Report]]

#lava
