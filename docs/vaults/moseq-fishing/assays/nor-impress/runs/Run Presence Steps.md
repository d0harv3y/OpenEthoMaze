---
title: Run Presence Steps
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
# Run Presence Steps

**Status:** computed — object-appearance **trial-step** clocks. #ladder #clock-portable  
**Parent:** [[H Syllable Task State]] · companion for [[V Engagement Delta]] / [[V Protocol Step Clocks]]

## Intent

Within-session object-appearance engagement steps (`frac_near` Δ and cousins); scalar condition Kruskal companions that replicate M `NOR_TX` engagement Δ. Threshold-reachable — no syllable alphabet required.

## Links

- Hypothesis: [[H Syllable Task State]]
- Verdicts: [[V Protocol Step Clocks]] · [[V Engagement Delta]]
- Upstream: [[Run Object Prox DR]] · [[Run Condition on Paired Delta]]
- Claim kind: **#clock-portable**

## Artifacts

**Campaign root:** `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_presence_steps/` ([[Campaign Roots]])

| File | Role |
|------|------|
| `presence_step_deltas_per_animal.csv` / `presence_step_tests_long.csv` | D/I — trial-step deltas |
| `presence_scalar_condition_kruskal_*.csv` | I — condition Kruskal companions |
| `presence_step_consensus_tests.csv` | Consensus companion |
| `INFO_presence_steps.md` | Data dictionary |

### Figures

| File | Role | Claim kind |
|------|------|------------|
| `figures/fig_presence_consensus_kruskal.svg` | Consensus Kruskal | #clock-portable |
| `figures/fig_presence_condition_kruskal.svg` | Condition panels | #clock-portable |
| vault `attachments/fig_v_protocol_step_presence_kruskal.svg` | Verdict embed | #clock-portable |

**Runner:** `OpenEthoMaze/scratch/nor_object_mi/` — presence-steps suite + `fig_simpler_first_presence.py`

## Related

- [[Run Session Paired]] · [[Run Object Prox DR]] · [[Run Condition on Paired Delta]]
- [[V Protocol Step Clocks]] · [[V Engagement Delta]]
