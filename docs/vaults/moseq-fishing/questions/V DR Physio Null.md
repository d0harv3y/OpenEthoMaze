---
title: V DR Physio Null
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
  - Q2 Honesty Pass
---
# V DR Physio Null

**Date:** 2026-09-23  
**Scope:** [[Run Crosscorr Spearman]] Spearman outs on disk (not re-run).  
**Gate:** between-animal Spearman; BH FDR `q_bh < 0.1` within panel; min `n ≥ 5`; prefer recognition / DR / `nvl_obj` over locomotion.

## Verdict

**Kill “NOR preference (DR) tracks physio” as a primary story** (and as a free-standing hunt). It does not honestly exist in these screens.

**Keep** a thin **exploratory** physio chapter: sparse associations are mostly **locomotor** (speed / distance / immobile) × sleep latency / NREM / factors — often on `no_obj` / `id_obj`, not novel preference. Useful as confound / arousal context.

**Gate for any new physio work:** lock a recognition-linked (or at least declared) condition-separating metric under [[H Recognition Separators]] first, then test **that** scalar vs physio.

## Design inventory (hit rates at q < 0.1, n ≥ 5)

| Design | Out folder | Tested cells | FDR hits | Hit rate | Honesty note |
|--------|------------|--------------|----------|----------|--------------|
| **physio × NOR (focused)** | `out_spearman_physio_x_bh` | 6912 | 33 | 0.48% | **Canonical screen.** Hits ≈ locomotor + some investigation counts/time; **0 DR hits**. 3/33 have `nvl` in feature name; none are discrimination ratio. |
| Same + IMPRESS SOL | `out_spearman_impress_sol/physio_x_bh` | 4800 | 16 | 0.33% | Same pattern; **0 nvl/DR-class hits** in FDR set. |
| Nested sleep↔cognitive (FDR) | `…/spearman_sleep_cognitive_nested_long.csv` | 273 | **1** | 0.37% | Sole hit: `SOL` × **`Fam_Total_Counts`** at `NOR_TX` / RBSD (ρ≈−0.58, n=34) — familiar counts, not DR. |
| Nested **nvl_obj** only | `…_nested_nvl_obj_long.csv` | 156 | **0** | 0% | Recognition-restricted nest empty. |
| Boss-repro nested (exp1) | `…_boss_repro_exp1_long.csv` | 315 | n/a | — | Stars are **`star_p05` (uncorrected)**. Pretty overviews (`overview_sleep_cognitive_nested_boss_repro_exp1*.png`) are **not** an FDR primary. 1 uncorrected DR star (GHSD REC3hr × Factor1, n=12). |
| Within-animal Δ×Δ | `out_spearman_change` | 6912 | 16 | 0.23% | All male; locomotor / investigation on id/no_obj; **0 DR/nvl**. |
| Mapped phase TX×sex | `out_spearman_tx_sex` | ~8992 | 27 | 0.30% | Redundant with focused screen. |
| NOR_TX × full PSG | `out_spearman_nor_tx_psg` | ~8992 | 17 | 0.19% | Same; male locomotorish. |
| TX×sex×**cohort** | `out_spearman/` | ~26k | 134 | 0.52% | **Demote.** Many \|ρ\|=1 at n=5–6 — unstable cells, not sellable. |
| Cluster13 Δshare BL→REC11 | `out_spearman_cluster13_bl_rec11` | 3150 | **0** | 0% | No FDR bridge. |
| Cluster2 Δshare (recog) | `out_spearman_cluster2_bl_rec11` | 1350 | 8 | 0.59% | Factor3 / logNREM × Δshare; model-scattered; not DR. Keep only as exploratory. |
| Full MoSeq syllable × physio | `out_spearman_moseq_physio` (15 models) | ~981k pooled | 1289 | 0.13% | **Demote fishing.** Alphabet × phases × strata; syllables not portable (ADR-0005). |

Expected false discoveries among *reported* FDR hits ≈ 10% of the hit list; screens with hit rate ≪ 10% are not “dense signal,” they are sparse survivors.

## What the 33 `physio_x_bh` hits actually are

- **Class:** ~15 `no_obj` + ~15 `id_obj` + **3** `nvl`-tagged (investigation duration/counts — **not DR**).
- **Physio side:** sleep-onset latencies, `logNREMdelta`, Factors, `Temp▲BL`.
- **NOR_TX subset (9 hits):** speed / immobile / distance / investigation on no_obj or id_obj; one `total_investigations|nvl_obj` × `LatencySec` (GHSD M, q≈0.08).
- **Arms:** RBSD/GHSD dominate hit list; not a clean noSD validation pattern.

## Locked claim language (use this)

> Across-animal Spearman screens (focused physio × NOR metrics; BH FDR within TX×sex×phase panels) do **not** support a primary association between **discrimination ratio / novel preference** and PSG summaries. Surviving FDR cells are sparse and dominated by **locomotor and non-recognition-trial** behavior. A single nested FDR hit links recovery sleep-onset latency to **familiar**-object investigation counts under RBSD — not novel preference.

## Keep / demote artifacts

| Keep (cite with caveat) | Demote / stop fishing |
|-------------------------|------------------------|
| `out_spearman_physio_x_bh` (+ README) as negative/sparse primary screen | `out_spearman/` cohort splits with n≈5 |
| Nested FDR tables (show empty nvl nest + Fam_Total_Counts caveat) | Full `out_spearman_moseq_physio` alphabet screens |
| Cluster13 **zero** as a clean negative | Uncorrected boss-repro stars as if FDR |
| Optional: one locomotor×latency example as arousal confound | Duplicate tx_sex / nor_tx_psg heatmaps in slides |

Boss-repro PNGs: keep in appendix only if caption says **uncorrected p** and points here.

## Next

1. Do **not** invent more physio×DR cuts without a pre-registered pairing.  
2. Engagement Δ × physio: done — **null in males** ([[V Engagement Physio Null]]).  
3. Lab **#1** remains recognition-linked separator ([[H Recognition Separators]]); physio stays parked until that locks (or until user deliberately picks another declared metric).

## Figure

Physio × NOR overview heatmap at NOR_TX / light — sparse locomotorish hits, not DR. Source: [[Run Crosscorr Spearman]].

![[fig_v_dr_physio_null_nor_tx_L.png]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[H Physio Coupling]]
- [[V Engagement Physio Null]]
- [[Run Crosscorr Spearman]]
- [[Prune Map]]
- [[NOR IMPRESS Index]]
- [[H Recognition Separators]]
- [[V Engagement Delta]]

#lava
