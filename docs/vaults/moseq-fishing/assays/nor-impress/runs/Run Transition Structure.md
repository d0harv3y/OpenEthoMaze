---
title: Run Transition Structure
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
# Run Transition Structure

**Status:** computed 2026-10-01 — Family [[F TransStruct-A]] **fail** ([[V TransStruct Null]]). #ladder  
**Parent (recog):** [[H Recognition Separators]] · **Also on:** [[H Non-Recognition Condition Separators]] (sequence redundancy)

## Intent

Per-animal bout-transition law at `NOR_TX` × `nvl_obj`: P(next \| current) → `trans_dist_to_nosd_ref` + `H_next_given_curr`; Family TransStruct-A (4 Kruskal cells).

## Links

- Family: [[F TransStruct-A]]
- Estimands: [[E TransStruct TV Distance]] · [[E TransStruct Conditional Entropy]]
- Verdict: [[V TransStruct Null]]
- Related: [[V TransStruct Cross-Campaign]] · [[V TransStruct Raw Exploratory]]

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_transition_structure/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `transition_structure_per_animal.csv` | D — 144 animals |
| `transition_structure_tests_long.csv` | I — 4 cells; 0 `hit_fdr05` |
| `INFO_transition_structure.md` | Data dictionary |
| `run_summary.json` | `pass_family_a: false` |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_transition_structure.py`  
**Lib / litmus:** `transition_structure.py`, `test_transition_structure.py`

### Exploratory cousins (not locks)

| Folder | Note |
|--------|------|
| `simpler_first_transition_structure_raw/` | [[V TransStruct Raw Exploratory]] |
| Recog / per-animal / downsampled | [[V TransStruct Cross-Campaign]] |

## Do not confuse with

[[Run Bout Grammar]] — nvl-prox **visit** counts/durations · [[Run Transition Structure Full Grid]] — all 12 levels
