---
title: Run NGramSeq Expanded
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
# Run NGramSeq Expanded

**Status:** computed — Family [[F NGramSeq-B]] **fail** ([[V NGramSeq Expanded Null]]). #ladder  
**Parent:** [[H Non-Recognition Condition Separators]]

## Intent

Fixed-budget pair MI / bigram richness at six expanded grains (parallel to TransStruct-B); 24-cell BH.

## Links

- Family: [[F NGramSeq-B]]
- Estimands: [[E NGramSeq Pair MI]] · [[E NGramSeq Bigram Richness]]
- Verdict: [[V NGramSeq Expanded Null]]
- Sibling: [[Run NGramSeq Full Grid]]

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_ngram_seq_expanded/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `ngram_seq_expanded_per_animal.csv` | D — animal × grain (+ `budget_M`) |
| `ngram_seq_expanded_tests_long.csv` | I — 24 cells; 0 FDR |
| `run_summary.json` | `pass_family_b: false` |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_ngram_seq_expanded.py`
