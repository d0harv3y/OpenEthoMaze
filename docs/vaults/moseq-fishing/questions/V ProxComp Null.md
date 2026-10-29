---
title: V ProxComp Null
type: verdict
assay: nor-impress
status: lava
claim_kind: mixed
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
  - mixed
---
# V ProxComp Null

**Date:** 2026-10-06  
**Scope:** [[Run ProxComp]] + time twin; session Δ on [[Run Prox Quad Session Delta]].  
**Claim kinds:** composition `#alphabet-bound`; `dr_time_prox` `#clock-portable`.

## Verdict

| Board | Litmus T1-assay | Condition Family A |
|-------|----------|--------------------|
| ProxComp-A (`dr_shannon_prox`, `dr_richness_prox`) | **pass** (sex=all) | **fail** 0/4 FDR |
| TimeProx-A (`dr_time_prox`) | **pass** (sex=all, median≈0.52) | **fail** 0/2 FDR |
| TimeQuad-A (`dr_time_quad`) on [[Run QuadComp]] | **pass** | **fail** 0/2 FDR |
| [[F ProxLevel-A]] (fam/nvl shannon–richness levels) | assay Δ pass (below) | **fail** 0/8 FDR |
| [[F QuadLevel-A]] on [[Run QuadComp]] | assay Δ pass | **fail** 0/8 FDR |
| SessDelta Kruskal Δ×condition (DR + time + levels) | — | **fail** 0 FDR ([[V Prox Quad SessDelta Null]]; Wilcoxon Δ vs 0 hits = dynamics only) |

## Constituents — litmus T1-assay vs litmus T1

Tokens: `fam_shannon_prox`, `nvl_shannon_prox`, `fam_richness_prox`, `nvl_richness_prox`.

**Litmus T1-assay** (paired nvl−fam in `noSD` @ `NOR_TX`, eligible) — assay preference:

| Kind | sex | n | med fam | med nvl | Δ | p | hit |
|------|-----|---|---------|---------|---|---|-----|
| shannon | all | 42 | 1.84 | 2.11 | +0.27 | 0.00056 | yes |
| shannon | F | 22 | 1.84 | 2.50 | +0.66 | 0.0083 | yes |
| shannon | M | 20 | 1.77 | 2.05 | +0.28 | 0.019 | yes |
| richness | all | 42 | 6 | 10 | +4 | 9e-7 | yes |
| richness | F | 22 | 6 | 10 | +4 | 5e-5 | yes |
| richness | M | 20 | 5 | 7.5 | +2.5 | 0.011 | yes |

**Litmus T1 / [[F ProxLevel-A]]** (Kruskal × condition within sex; BH m=8, confirmatory after peek): **0/8** `hit_fdr05`, **0/8** `hit_p05`. Best ≈ M `fam_richness_prox` p≈0.16 (q≈0.72). Same T1-assay-pass / T1-fail mismatch as the DR-cousin Family A — naming was just lagged.

## Locked language

> Exclusive 0.10 m prox and object-quadrant ROIs both show novel preference in controls for time and repertoire (DR cousins **and** fam/nvl Shannon–richness constituents). Neither composition DR cousins, time twins, nor absolute level families (ProxLevel-A / QuadLevel-A) separate `condition` at `NOR_TX`. Session rises (esp. time twins BL→TX) are protocol dynamics; condition does not modulate those Δ under SessDelta BH.

Do not open grammar on these nulls. Per-model raw alphabet grid: [[V Prox Quad Per Model Null]] (consensus fail; 1/21 lone Quad FDR not promoted).

## Related

- [[F ProxComp-A Score Contract]] · [[F ProxLevel-A]] · [[F QuadLevel-A]] · [[F QuadComp-A]] · [[V QuadComp Null]]
- [[V ProxComp Per-Scalar Null]] — same strip, one BH family per scalar (also fail)
- [[Run Prox Quad Per Model]] · [[V Prox Quad Per Model Null]]
- [[H Novelty Preference DR]] · [[H Investigation Quality]]
