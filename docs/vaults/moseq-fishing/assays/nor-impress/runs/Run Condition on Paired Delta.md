---
title: Run Condition on Paired Delta
type: run
assay: nor-impress
status: treasure
claim_kind: mixed
verdict: pass
tags:
  - claim/run
  - assay/nor-impress
  - treasure
  - mixed
---
# Run Condition on Paired Delta

**Status:** computed — engagement Δ **locked** ([[V Engagement Delta]]); novelty lattice **null** ([[V Recognition Lattice Null]]). #ladder / #treasure #clock-portable  
**Parent:** [[H Recognition Separators]] · also [[H Non-Recognition Condition Separators]] (engagement side board)

## Intent

Condition Kruskal on paired within-animal Δs (trial-step / session-step) — primary home of M `NOR_TX` object-appearance `delta_frac_near`.

## Links

- Verdict (keep): [[V Engagement Delta]]
- Verdict (lattice null): [[V Recognition Lattice Null]]
- Companions: [[Run Presence Steps]] · [[Run Session Paired]] · [[Run Composition Companion Audit]]
- Claim kind: **#clock-portable** (engagement Δ / occupancy); alphabet DA / Shannon agreement panels on disk are #alphabet-bound companions — not the lock

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_condition_on_paired_delta/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `condition_consensus_animal_session_tests_long.csv` | I — consensus-animal session-step Kruskal |
| `condition_*_tests*.csv` / agreement tables | I — model-level + agreement |
| `INFO_condition_on_paired_delta.md` | Data dictionary (header path strings may say `tx_`; folder is `condition_on_*`) |

### Figures

| File | Role | Claim kind |
|------|------|------------|
| `figures/fig_q5_engagement_delta_nor_tx_m.svg` | Locked M engagement Δ slide | #clock-portable |
| `figures/fig_q5_engagement_delta_nor_tx_f.svg` | F companion (FDR miss) | #clock-portable |
| vault `attachments/fig_q5_engagement_delta_nor_tx_{m,f}.svg` | Obsidian embeds on [[V Engagement Delta]] | #clock-portable |
| `figures/fig_condition_scalar_condition_agreement.svg` | Scalar agreement overview | mixed |
| `figures/fig_condition_q*_*.svg` | DA / Shannon agreement companions | #alphabet-bound |
| `figures/FIGURES.md` | Full inventory | — |

**Runner / slides:** `OpenEthoMaze/scratch/nor_object_mi/` — condition-on-paired-delta suite + `fig_q5_engagement_delta_slide.py`

**Demote:** `simpler_first_condition_on_paired_delta_parametric/` — [[Prune Map]]

## Related

- [[V Engagement Delta]] · [[NOR IMPRESS Index]] · [[Claim Kind]]
- [[Run Presence Steps]] · [[Run Session Paired]]
