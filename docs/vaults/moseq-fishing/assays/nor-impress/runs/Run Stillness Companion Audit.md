---
title: Run Stillness Companion Audit
type: run
assay: nor-impress
status: ladder
claim_kind: clock-portable
verdict: pass
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - clock-portable
---
# Run Stillness Companion Audit

**Status:** computed — audit of slides_pack `frac_still` level Kruskal; [[F Stillness-Companion-A]] **pass** (2/2).  
**Verdict:** [[V Protocol Step Clocks]]  
**Parent:** [[H Non-Recognition Condition Separators]]  
**Claim kind:** #clock-portable

## Intent

Re-declare BH on the pre-selected recovery-acclimation stillness cells (`NOR_REC3hr` × `no_obj` × {F,M}) already computed in slides_pack — no stillness recompute.

## Links

- Family: [[F Stillness-Companion-A]]
- Verdict: [[V Protocol Step Clocks]]
- Twin (alphabet): [[F Composition-Companion-B]] / [[Run Composition Companion Audit]]
- Upstream: [[Run Slides Pack]] (`frac_still/`)

## Artifacts

**Audit out:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_stillness_companion_audit/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `stillness_companion_a_tests.csv` | Family A (2 cells; 2/2 FDR under m=2) |
| `run_summary.json` | pass flag |

**Upstream (read-only):**

| Path | Role |
|------|------|
| `…/slides_pack/frac_still/frac_still_kruskal.csv` | Level Kruskal (24-cell BH parent lattice) |

**Note:** Audit CSV written from the locked cells + BH-m=2 recompute (same pattern as [[Run Composition Companion Audit]]); no separate Python runner required for this 2-cell extract.
