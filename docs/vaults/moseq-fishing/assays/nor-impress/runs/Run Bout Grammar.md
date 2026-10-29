---
title: Run Bout Grammar
type: run
assay: nor-impress
status: ladder
claim_kind: na
verdict: fail
tags:
  - claim/run
  - assay/nor-impress
  - ladder
---
# Run Bout Grammar

**Status:** computed 2026-09-23 — Family BoutGrammar-A **fail** ([[V Visit Grammar Null]]). #ladder  
**Parent:** [[H Recognition Separators]] · also [[H Investigation Quality]]

## Intent

Per-animal novel-prox visit grammar (counts / durations) at r = 0.10 m; 24 Kruskal cells.

## Links

- Estimand: [[E Visit Grammar Counts]]
- Verdict: [[V Visit Grammar Null]]
- Hypothesis: [[H Recognition Separators]]

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_bout_grammar/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `bout_grammar_per_animal.csv` | D — per-animal visit scalars |
| `bout_grammar_tests_long.csv` | I — BoutGrammar-A (0 FDR) |
| `INFO_bout_grammar.md` | Data dictionary |
| `run_summary.json` | Knobs + pass/fail |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_bout_grammar.py`  
**Litmus:** `test_bout_grammar.py`

## Related

- [[Run Object Prox DR]] — same r; different scalar (DR / occupancy)
- [[Run Side Mass]] — geometry cousin (also fail)
- [[V Candidate Lattice Null]]
