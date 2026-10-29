---
title: Run NGramSeq Full Grid
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
# Run NGramSeq Full Grid

**Status:** computed — Family [[F NGramSeq-C]] **fail** ([[V NGramSeq Full Grid Null]]). #ladder  
**Parent:** [[H Non-Recognition Condition Separators]]

## Intent

Fixed-budget pair MI / bigram richness at **all 12** NOR level grains; 48-cell BH.

## Links

- Family: [[F NGramSeq-C]]
- Estimands: [[E NGramSeq Pair MI]] · [[E NGramSeq Bigram Richness]]
- Verdict: [[V NGramSeq Full Grid Null]]
- Siblings: [[Run NGramSeq]] · [[Run NGramSeq Expanded]]

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_ngram_seq_full_grid/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `ngram_seq_full_grid_per_animal.csv` | D — animal × 12 grains |
| `ngram_seq_full_grid_tests_long.csv` | I — 48 cells; 0 FDR |
| `run_summary.json` | `pass_family_c: false` |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_ngram_seq_full_grid.py`
