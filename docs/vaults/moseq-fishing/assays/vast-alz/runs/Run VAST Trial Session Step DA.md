---
title: Run VAST Trial Session Step DA
type: run
assay: vast-alz
status: ladder
claim_kind: na
verdict: na
tags:
  - claim/run
  - assay/vast-alz
  - ladder
---
# Run VAST Trial Session Step DA

**Status:** computed — trial-step / session-step DA volcanos. #ladder  
**Assay:** [[VAST Alz Index]]

## Intent

Paired Δp on **trial-steps** (within `session`, pair `trial_window`) and **session-steps** (within `trial_window`, pair `session`). Grain: animal × session × trial_window; composition = frame share; pass 1 = `interval=run`. VAST windows — not NOR `no_obj`/`id_obj`/`nvl_obj`.

## Links

- Upstream: [[Run VAST Syllable Signatures]]
- Pattern: [[Simpler-First Ladder Pattern]]
- Index: [[VAST Alz Index]]

## Artifacts

**Campaign root:** `D:\az-sd-vast_paramscan2026\_da_trial_windows\` ([[Campaign Roots]])

| File | Role |
|------|------|
| DA tables | I — trial/session-step Δp + BH |
| `*_overlay_*_steps` figures | Pooled ladders |
| `*_stratified_*_steps_{wt_na,wt_RBSF-1,tg_na,tg_RBSF-1}` | One figure per strain×tx |
| `INFO_da.md` | Data dictionary |

**Runners:**
- `OpenEthoMaze/scratch/vast_moseq/regen_da_trial_windows.py` — tables
- `OpenEthoMaze/scratch/vast_moseq/fig_da_trial_windows.py` — volcanos
- strat helper: `vast_da_strat.py`

## Related

- [[Run VAST Syllable Signatures]] · [[Simpler-First Ladder Pattern]] · [[VAST Alz Index]]
