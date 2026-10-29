---
title: Run Session Paired
type: run
assay: nor-impress
status: ladder
claim_kind: mixed
verdict: na
tags:
  - claim/run
  - assay/nor-impress
  - ladder
  - mixed
---
# Run Session Paired

**Status:** computed — within-animal session steps. #ladder  
**Parent:** [[H Syllable Task State]] · honesty: [[V Protocol Step Clocks]] (scalars) · [[V Composition Step Fishing]] (DA / cluster)

## Intent

Within-animal **session-steps** (e.g. BL→TX, condition→REC): scalars (`frac_near`, Shannon, …) + DA + cluster Kruskal. Session rise ≠ SD efficacy; condition fishing sparse except trajectory companions.

## Links

- Hypothesis: [[H Syllable Task State]]
- Verdicts: [[V Protocol Step Clocks]] · [[V Composition Step Fishing]]
- Companions: [[Run Presence Steps]] · [[Run Condition on Paired Delta]] · [[Run Simpler First DA]]
- Claim kind: **mixed** — scalar occupancy/engagement #clock-portable; Shannon/DA/cluster #alphabet-bound

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_session_paired/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `session_paired_tests_long.csv` / `session_paired_deltas_per_animal.csv` | D/I — session-step scalars |
| `session_paired_scalar_condition_kruskal_*.csv` | I — condition on session Δ |
| `session_paired_da_tests_*.csv` | I — session-step DA |
| `session_paired_cluster_condition_kruskal*.csv` | I — cluster session-step |
| `INFO_session_paired.md` | Data dictionary |

### Figures

| File | Role | Claim kind |
|------|------|------------|
| `figures/fig_session_paired_cluster_condition_kruskal_overview.svg` | Cluster condition overview | #alphabet-bound |
| `figures/fig_session_paired_*` | Full slide deck | mixed |
| vault `attachments/fig_v_session_step_cluster_kruskal.svg` | Verdict embed | #alphabet-bound |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/` — session-paired suite + `fig_simpler_first_session_paired.py`

## Related

- [[Run Presence Steps]] · [[Run Condition on Paired Delta]] · [[Run Simpler First DA]]
- [[V Protocol Step Clocks]] · [[V Composition Step Fishing]]
