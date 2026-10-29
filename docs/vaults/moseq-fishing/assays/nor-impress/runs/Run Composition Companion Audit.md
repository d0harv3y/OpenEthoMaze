---
title: Run Composition Companion Audit
type: run
assay: nor-impress
status: ladder
claim_kind: na
verdict: pass
tags:
  - claim/run
  - assay/nor-impress
  - ladder
---
# Run Composition Companion Audit

**Status:** computed — audit of consensus tables; [[F Composition-Companion-A]] **pass** · [[F Composition-Companion-B]] **partial**.  
**Verdict:** [[V Composition Companion Partial]]  
**Parent:** [[H Non-Recognition Condition Separators]]

## Intent

Re-declare BH on pre-selected session-step / Shannon-level cells already computed in the condition_on_paired_delta + slides_pack consensus artifacts — no composition recompute.

## Links

- Families: [[F Composition-Companion-A]] · [[F Composition-Companion-B]]
- Verdict: [[V Composition Companion Partial]]
- Upstream: [[Run Condition on Paired Delta]] · [[Run Slides Pack]] (`shannon/`)

## Artifacts

**Audit out:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_composition_companion_audit/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `composition_companion_a_tests.csv` | Family A (4 cells; 4/4 FDR) |
| `composition_companion_b_tests.csv` | Family B (2 cells; 1/2 FDR) |
| `run_summary.json` | pass flags |

**Upstream (read-only):**

| Path | Role |
|------|------|
| `…/simpler_first_condition_on_paired_delta/condition_consensus_animal_session_tests_long.csv` | Session-step consensus Kruskal |
| `…/slides_pack/shannon/shannon_level_kruskal.csv` | Shannon level consensus |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_composition_companion_audit.py`
