---
title: V Engagement Physio Null
type: verdict
assay: nor-impress
status: lava
claim_kind: na
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
aliases:
  - Q2 Engagement Physio Honesty Pass
---
# V Engagement Physio Null

**Date:** 2026-09-24  
**Scope:** confirmatory between-animal Spearman of the **Q5-locked engagement Δ** × focused physio (same gate as [[V DR Physio Null]]).  
**Out:** [[Run Crosscorr Spearman]] → `out_spearman_engagement_delta_physio/`  
**Regen:** see that Run note.

## Declared design (before looking at q)

| Knob | Choice |
|------|--------|
| Behavior | Consensus median-across-21-models `delta_frac_near` @ `NOR_TX`, `full_session` × `frame_share` |
| Features | **Locked:** `engΔ\|obj_appear` (`no_obj→id_obj`), `engΔ\|span_nvl` (`no_obj→nvl_obj`). **Control:** `engΔ\|novelty` (`id_obj→nvl_obj`) |
| Physio | Focused set: Temp▲BL, Activity, Factor1–3, logNREMdelta, LatencySec / LatencyConsec60Sec / LatencyCum120Sec / SOL |
| Phys phases | L, D, T, R (each phase its own panel grid) |
| Stratification | `condition` (TX) × sex within panel |
| Association | Across-animal Spearman ρ |
| Hit rule | BH `q_bh < 0.1` within panel; min pairwise `n ≥ 5` |

Primary interest: **males** (engagement condition-separates only in M — [[V Engagement Delta]]).

## Verdict

**Male engagement Δ does not track focused physio under this gate.**

- Cells tested: **648**  
- FDR hits (all features / sexes): **4** (0.6%)  
- FDR hits on **locked** steps: **1** — and it is **female**, not male  
- FDR hits **M × locked**: **0** (best male locked q ≈ **0.16**)

Do **not** sell “SD-blunted object-appearance engagement reflects sleep/physio” from this screen. Engagement remains a **behavior-only** condition side claim.

## The four FDR survivors (exploratory only)

| phys | TX | sex | feature | phys metric | ρ | q | n |
|------|----|-----|---------|-------------|---|---|---|
| T | RBSD | F | `engΔ\|span_nvl` (**locked**) | LatencyCum120Sec | −0.83 | 0.007 | 14 |
| R | noSD | F | `engΔ\|novelty` (control) | Factor2 | +0.68 | 0.026 | 18 |
| R | noSD | F | `engΔ\|novelty` (control) | logNREMdelta | +0.69 | 0.026 | 18 |
| L | noSD | F | `engΔ\|novelty` (control) | logNREMdelta | +0.63 | 0.028 | 24 |

**Read carefully:** three of four hits are on the **novelty** control column (condition Kruskal miss at TX). The single locked-step hit is F/RBSD sleep-latency vs span engagement — small n, opposite sex from the condition lock, not replicated across phases. Treat as sparse noise / appendix, not a bridge chapter.

## Locked claim language

> Within males, consensus object-appearance engagement Δ at `NOR_TX` does **not** associate with focused PSG/physio summaries after BH FDR within TX×sex×phys-phase panels (0 hits; min q≈0.16). Sparse female FDR cells exist but do not support a primary engagement×physio story.

## Artifacts

| Path | Role |
|------|------|
| `tables/spearman_long.csv` | Full long table |
| `heatmaps/overview_engagement_delta_phys{L,D,T,R}.png` | Panel overviews |
| `README.txt` | Gate + hit counts |

## Figure

Engagement Δ × physio overview (light phase) — M×locked null. Source: [[Run Crosscorr Spearman]].

![[fig_v_engagement_physio_null_L.png]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[H Physio Coupling]]
- [[V DR Physio Null]] — DR×physio already kill; this note = engagement follow-up
- [[V Engagement Delta]] — behavior lock used as X
- [[Run Crosscorr Spearman]]
- [[Prune Map]]
- [[NOR IMPRESS Index]]

#lava
