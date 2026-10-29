---
title: Run Sequence PerGrain BH
type: run
assay: nor-impress
status: ladder
claim_kind: alphabet-bound
verdict: na
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - alphabet-bound
---
# Run Sequence PerGrain BH

**Status:** computed 2026-10-05 — multiplicity audit only. #ladder #alphabet-bound  
**Parent:** [[F TransStruct-PerGrain]] · [[F NGramSeq-PerGrain]]

## Intent

Re-apply Benjamini–Hochberg (**BH**) **per grain** (m=4: sex × 2 metrics) on existing TransStruct / NGramSeq `*_tests_long.csv` Kruskal **p** columns. Does **not** recompute scalars. Makes B/C panels commensurate with Family A.

## Links

- Families: [[F TransStruct-PerGrain]] · [[F NGramSeq-PerGrain]]
- Verdicts: [[V TransStruct PerGrain Null]] · [[V NGramSeq PerGrain Null]]
- Spec: [[Joint vs Per-Grain FDR]]
- Upstream joint Runs: [[Run Transition Structure Full Grid]] · [[Run Transition Structure Expanded]] · [[Run NGramSeq Full Grid]] · [[Run NGramSeq Expanded]]

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_sequence_per_grain_bh/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `transstruct_full_grid_per_grain_tests_long.csv` | Per-grain BH on C panel (primary) |
| `transstruct_full_grid_per_grain_rollup.csv` | Grain pass / min p / min q |
| `ngramseq_full_grid_per_grain_tests_long.csv` | Per-grain BH on NGramSeq-C |
| `ngramseq_full_grid_per_grain_rollup.csv` | Grain rollup |
| `*_expanded_per_grain_*.csv` | Optional B-panel companion |
| `run_summary.json` | Pass counts |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_sequence_per_grain_bh.py`

## Outcome (primary full grid)

| Scalar family | Grains pass | Cell FDR hits |
|---------------|-------------|-----------------|
| TransStruct | 0/12 | 0 |
| NGramSeq | 0/12 | 0 |

## Related

- [[Joint vs Per-Grain FDR]] · [[H Non-Recognition Condition Separators]]
