---
title: V Prox Quad Per Model Null
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
# V Prox Quad Per Model Null

**Date:** 2026-10-06  
**Scope:** [[Run Prox Quad Per Model]] — exploratory raw_syllable_id grid (21 models).  
**Not a replacement** for locked [[V QuadComp Null]] / [[V ProxComp Null]] (`cluster_id`).

## Verdict

**Fail to promote.** Consensus QuadComp-raw / ProxComp-raw: **0/4 FDR** each. ProxComp-raw within-model: **0/21** FDR. QuadComp-raw: **1/21** lone hit (F `dr_shannon_quad` on `paramscan_s1-1e8_s2-3e4_ss-100`, q≈0.028) — not portable, consensus miss, do not invent Family B.

Litmus T1-assay sex=all hit rate **1.0** across models for DR cousins (assay asymmetry reproduces under raw alphabets). Per-animal / consensus tables also carry constituents `fam_shannon_*`, `nvl_shannon_*`, `fam_richness_*`, `nvl_richness_*`, and Hill q=2 companions `fam_hill2_*` / `nvl_hill2_*` / `dr_hill2_*` (panel D; Family A stays shannon+richness DR-only).

Figure packs (cluster / consensus / per-model, level + session-step): [[Run Prox Quad Comp Figs]] · [[Run Prox Quad Session Step Figs]].

## Locked language

> Per-model raw_syllable_id QuadComp / ProxComp composition DR cousins do not yield a consensus condition separator. One of 21 models shows a single QuadComp-raw FDR cell; that is exploratory noise relative to the locked cluster_id nulls and the consensus fail.

## Related

- [[Run Prox Quad Per Model]] · [[V QuadComp Null]] · [[V ProxComp Null]]
- [[V Prox Quad Per Animal Exploratory]] · [[H Investigation Quality]]
