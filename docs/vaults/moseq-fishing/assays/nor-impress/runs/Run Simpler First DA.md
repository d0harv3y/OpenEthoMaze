---
title: Run Simpler First DA
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
# Run Simpler First DA

**Status:** computed — syllable differential abundance (DA) + FDR. #ladder #alphabet-bound  
**Parent:** [[H Syllable Task State]] · honesty: [[V Composition Step Fishing]]

## Intent

Alphabet DA (frame-share / bout weighting) and cluster-mapped condition Kruskal. Charted for task-state; **not** a portable recognition / condition lock (ADR-0005).

## Links

- Hypothesis: [[H Syllable Task State]]
- Verdict: [[V Composition Step Fishing]]
- Companions: [[Run Session Paired]] · [[Run Condition on Paired Delta]] · [[Run Slides Pack]]
- Claim kind: **#alphabet-bound**

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_da/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `da_syllable_tests_long.csv` / `da_syllable_tests_condition_sex.csv` | I — syllable Δp × condition / steps |
| `cluster_condition_kruskal*.csv` | I — HDBSCAN cluster condition Kruskal |
| `INFO_da.md` · `INFO_cluster_condition_kruskal.md` | Data dictionaries |
| `run_summary.json` | Knobs |

### Figures

| File | Role | Claim kind |
|------|------|------------|
| `figures/fig_da_n_hit_fdr05.png` | FDR hit counts | #alphabet-bound |
| `figures/fig_da_volcano_ladder_overlay_tx.png` | Challenge volcano overlay | #alphabet-bound |
| `figures/fig_da_volcano_*.svg` | Per-session volcanos | #alphabet-bound |
| `fig_cluster_condition_kruskal_overview.svg` | Cluster Kruskal overview | #alphabet-bound |
| vault `attachments/fig_v_composition_step_*` | Verdict embeds | #alphabet-bound |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/` — simpler-first DA suite + `fig_simpler_first_da.py`

**Demote:** `simpler_first_da_bout_count/` · `simpler_first_nested_da/` — [[Prune Map]]

## Related

- [[V Composition Step Fishing]] · [[Run Session Paired]] · [[Run Condition on Paired Delta]] · [[Prune Map]]
