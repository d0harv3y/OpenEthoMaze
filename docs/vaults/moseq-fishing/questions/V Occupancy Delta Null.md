---
title: V Occupancy Delta Null
type: verdict
assay: nor-impress
status: lava
claim_kind: clock-portable
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
  - clock-portable
aliases:
  - Q5 Occupancy Session-Delta Honesty Pass
---
# V Occupancy Delta Null

**Date:** 2026-09-23  
**Scope:** [[Run Occupancy Session Delta]] / Family OccSessDelta-A ([[E Occupancy Session Delta]]).  
**Gate:** Kruskal on BL→TX Δ `frac_near_nvl` / `frac_near_fam` by `condition` within sex; `hit_fdr05` within 4-cell BH family.  
**Claim kind:** #clock-portable

## Verdict

**Fail.** Zero `hit_fdr05`. Male `delta_frac_near_nvl` is the only `hit_p05` (p≈0.034 → **q≈0.135**). Same honesty neighborhood as TX-level `frac_near_nvl` (q≈0.12 in Candidates Family A).

Do not invent Family B (extra session steps) without user OK.

## Near miss

M `delta_frac_near_nvl`: p≈0.034, q≈0.135 → [[V Near Misses Watchlist]] (rule `p < 0.05`, `0.1 < q_bh < 0.2`). Not a lock.

## Locked negative language

> Condition does **not** modulate the BL→TX rise in novel-prox occupancy under the declared OccSessDelta-A BH family (0/4 `hit_fdr05`). Directionally, noSD females rise most and RBSD males least, but FDR does not keep the male novel-Δ cell.

## Evidence

Full paths + runner → [[Run Occupancy Session Delta]].

| sex | metric | p | q_bh | hit_fdr05 | median Δ noSD / GHSD / RBSD |
|-----|--------|---|------|-----------|------------------------------|
| M | `delta_frac_near_nvl` | 0.034 | **0.135** | **False** | +0.038 / +0.038 / −0.018 |
| F | `delta_frac_near_nvl` | 0.074 | 0.148 | False | +0.151 / +0.073 / +0.033 |
| F | `delta_frac_near_fam` | 0.157 | 0.209 | False | … |
| M | `delta_frac_near_fam` | 0.565 | 0.565 | False | … |

**Peek caveat:** uncorrected p on novel Δ were seen in chat before the contract; BH q remains the gate.

## Figure

Honesty panel — OccSessDelta-A. Source: [[Run Occupancy Session Delta]].

![[fig_v_occupancy_delta_null.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[E Occupancy Session Delta]]
- [[V Candidate Lattice Null]] — TX level cousin
- [[V Recognition Lattice Null]]
- [[Run Occupancy Session Delta]]
- [[Run Object Prox DR]]
- [[NOR IMPRESS Index]]

#lava
