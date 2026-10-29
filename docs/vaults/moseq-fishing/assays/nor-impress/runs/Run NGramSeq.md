---
title: Run NGramSeq
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
# Run NGramSeq

**Status:** computed 2026-10-02 — Family [[F NGramSeq-A]] **fail** ([[V NGramSeq Null]]). #ladder  
**Parent (recog flavor):** [[H Recognition Separators]] · **Redundancy:** [[H Non-Recognition Condition Separators]]

## Intent

Fixed-budget pair MI + bigram richness at `NOR_TX` × `nvl_obj` (M=108, seed 7); 4-cell BH. Reference-free.

## Links

- Family: [[F NGramSeq-A]]
- Estimands: [[E NGramSeq Pair MI]] · [[E NGramSeq Bigram Richness]]
- Verdict: [[V NGramSeq Null]]
- Expanded: [[Run NGramSeq Expanded]] · [[Run NGramSeq Full Grid]]

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_ngram_seq/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `ngram_seq_per_animal.csv` | D — 144 animals |
| `ngram_seq_tests_long.csv` | I — 4 cells; 0 FDR |
| `INFO_ngram_seq.md` | Data dictionary |
| `run_summary.json` | `pass_family_a: false` |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_ngram_seq.py`  
**Lib / litmus:** `ngram_structure.py`, `test_ngram_structure.py`

### Cross-campaign exploratory

Grid / per-animal runners under same `_nor_object_mi/` — see [[V NGramSeq Null]] § Cross-campaign.
