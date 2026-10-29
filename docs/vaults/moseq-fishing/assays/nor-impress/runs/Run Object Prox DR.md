---
title: Run Object Prox DR
type: run
assay: nor-impress
status: ladder
claim_kind: clock-portable
verdict: na
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - clock-portable
---
# Run Object Prox DR

**Status:** computed — exclusive object-prox DR at r = 0.10 m. #ladder #clock-portable  
**Parent:** [[H Assay Validity NOR]] · [[H Novelty Preference DR]]

## Intent

Exclusive DR from 0.10 m fam/nvl prox windows; Wilcoxon vs 0; Kruskal by condition within sex. Upstream for occupancy Δ / candidates lattice.

## Links

- Hypotheses: [[H Assay Validity NOR]] · [[H Novelty Preference DR]]
- Lattice: [[V Recognition Lattice Null]] · [[V Candidate Lattice Null]]
- Downstream: [[Run Occupancy Session Delta]] · [[Run Bout Grammar]]
- Claim kind: **#clock-portable**

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_object_prox_0p10/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `object_prox_*` / `object_prox_consensus_tests.csv` | D / I — per-model + consensus DR / `frac_near_*` |
| `INFO_object_prox.md` | Data dictionary |

### Figures

| File | Role | Claim kind |
|------|------|------------|
| `figures/fig_object_prox_violin_dr.svg` | DR violins | #clock-portable |
| `figures/fig_object_prox_consensus_wilcoxon.svg` | DR vs 0 (assay validity) | #clock-portable |
| `figures/fig_object_prox_consensus_kruskal.svg` | DR × condition | #clock-portable |
| `figures/fig_object_prox_occupancy_{nvl,fam}.svg` | Occupancy clocks | #clock-portable |
| `figures/fig_object_prox_condition_kruskal.svg` | Condition Kruskal panels | #clock-portable |
| `figures/FIGURES.md` | Full inventory | — |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/simpler_first_object_prox.py`

## Related

- [[Run Classic DR]] · [[Run Protocol Prologue]] · [[Claim Kind]]
- [[NOR IMPRESS Index]]
