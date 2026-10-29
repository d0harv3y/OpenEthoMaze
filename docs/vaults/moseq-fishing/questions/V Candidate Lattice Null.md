---
title: V Candidate Lattice Null
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
  - Q5 Candidates Honesty Pass
---
# V Candidate Lattice Null

**Date:** 2026-09-23  
**Scope:** next candidates after [[V Recognition Lattice Null]] — (1) declared `frac_near_nvl` occupancy family, (2) spatial / quadrant, (3) Q4 investigation-quality scalars.  
**Gate:** pre-name family → Kruskal (or Welch ANOVA where already declared) → Benjamini–Hochberg (BH) `q_bh < 0.05`. Uncorrected `hit_p05` alone is not a lock.

## Verdict

**All three candidates fail.** Recognition-linked condition separation remains **not locked**. The only honest condition separator on the shelf is still male object-appearance engagement Δ ([[V Engagement Delta]]) — not recognition.

Do not reopen physio ([[H Physio Coupling]]) on these metrics.

---

## 1. Declared occupancy family (`frac_near_nvl` / fam)

**Source:** [[Run Object Prox DR]] → `object_prox_consensus_tests.csv` (median across 21 kpMS models, then Kruskal by condition within sex).

**Declared Family A (primary):** `NOR_TX` × sex ∈ {F,M} × metric ∈ {`frac_near_nvl`, `frac_near_fam`} → **4 tests**, BH within family.

| sex | metric | p | q_bh | hit_fdr05 | median noSD / GHSD / RBSD |
|-----|--------|---|------|-----------|---------------------------|
| M | `frac_near_nvl` | 0.030 | **0.121** | **False** | 0.274 / 0.201 / 0.127 |
| F | `frac_near_nvl` | 0.208 | 0.415 | False | 0.279 / 0.226 / 0.222 |
| M | `frac_near_fam` | 0.648 | 0.814 | False | … |
| F | `frac_near_fam` | 0.814 | 0.814 | False | … |

**Family B** (all 4 sessions × same 2 metrics × 2 sex = 16): **0** FDR hits; lowest q≈0.20 (REC11 F `frac_near_nvl`).  
**Family C** (NOR_TX + `dr_exclusive` = 6): **0** FDR hits; M `frac_near_nvl` q≈0.18.

**Read:** The previously noted male `frac_near_nvl` `hit_p05` **does not survive** a minimal declared BH family. Absolute novel-prox occupancy is **not** an honest condition separator. Prefer novel *share* (DR) remains null ([[H Novelty Preference DR]]).

**Near miss:** M `frac_near_nvl` p≈0.030, q≈0.121 → [[V Near Misses Watchlist]] (`0.1 < q_bh < 0.2`). Not a lock.

**Classic investigation seconds** (`t_nvl_s` / `t_fam_s` from `protocol_dr_per_animal.csv`) at `NOR_TX`: M `t_nvl_s` p≈0.10 — miss even uncorrected; included in Q4 family below.

---

## 2. Spatial / quadrant

**On disk:** `syllable_spatial_heatmaps*` (+ `…_cluster13_condition_overlay`) — **descriptive (D)** arena dwell maps; grain = pooled session × trial × sex; color = condition. **No per-animal spatial scalar table. No Kruskal / FDR.**

**Descriptive note only (not I):** cluster-13 condition-overlay dwell *share* at `NOR_TX` `nvl_obj` M ≈ noSD 0.28 / GHSD 0.33 / RBSD 0.39 (RBSD *higher* mass) — opposite direction from engagement Δ, wrong grain for a condition claim, cluster-filtered.

**Quadrant score:** **not implemented.** Prune Map still correct: define animal × `nvl_obj` quadrant (or fam-left / nvl-right mass) *before* claiming.

**Verdict:** spatial campaign cannot lock Q5 until a **per-animal** geometry score exists and passes a declared family. Heatmaps stay illustration-only.

---

## 3. Q4 investigation quality

### 3a. Declared protocol family @ `NOR_TX`

**Source:** [[Run Protocol Prologue]] → `protocol_dr_per_animal.csv`.  
**Family:** sex ∈ {F,M} × metric ∈ {`t_nvl_s`, `t_fam_s`, `invest_asym_s` (= t_nvl−t_fam), `mean_speed_mps`, `time_immobile_s`, `distance_m`, `frac_near_nvl`, `frac_near_fam`} → **16 tests**, BH.

**Result:** **0** `hit_fdr05`. Smallest p = M `frac_near_nvl` 0.030 → q_bh ≈ **0.48** inside this larger family. Classic investigation time and locomotor confounds do not separate arms.

### 3b. Four-mask hunt (already declared in INFO)

**Source:** `simpler_first_four_mask/hunt_tests.csv` (demoted folder — [[Prune Map]]; no Run hub).  
**Primary:** Welch ANOVA of (TX−BL) by condition on `nvl_obj` within sex; BH = 4 masks × 2 metrics within sex.  
**Result:** **0** `hit_fdr05` (primary min p≈0.055, q≈0.19). Protocol/gate companions also 0 FDR. Demoted for story ([[Prune Map]]).

### 3c. INFO / prox MI joins

Already negative in [[V Recognition Lattice Null]]: `info_dr_pause` MI FDR miss; nearest-prox MI FDR miss. Not investigation-quality separators.

### 3d. Kinematics / signatures

Infrastructure / ADR-0005 only ([[Run Syllable Kinematics]], [[Run Syllable Signatures]]) — no ready animal × condition × recognition Kruskal lattice to honesty-test without a new score definition.

**Q4 status:** still invented interest; audited candidates **fail** the condition-separation litmus.

---

## Keep / demote

| Keep | Demote |
|------|--------|
| Explicit null: Family A table (occupancy BH fail) | Selling M `frac_near_nvl` `hit_p05` as locked |
| Engagement Δ side claim ([[V Engagement Delta]]) | Spatial heatmaps as condition evidence |
| four_mask / Q4 as documented negatives | Reopening physio on these fails |

## What this closes / leaves open

| Closed | Still open (needs new compute) |
|--------|--------------------------------|
| Occupancy BH family | Per-animal **quadrant / side-mass** score + declared family |
| Classic investigation time × condition | Bout grammar near nvl (duration, approach–leave) with portable definition |
| Four-mask TX−BL×condition | Residual of DR after locomotor regression (only if residual separates) |

## Figure

Object-prox occupancy Kruskal (consensus) — Family A near-miss zone, 0 FDR. Source: [[Run Object Prox DR]].

![[fig_v_candidate_lattice_occupancy.svg]]

Regen / campaign copies: `sack/.../vault_verdict_figures/` · `scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`.

## Related

- [[H Recognition Separators]]
- [[V Recognition Lattice Null]]
- [[V Engagement Delta]]
- [[H Investigation Quality]]
- [[H Novelty Preference DR]]
- [[Run Object Prox DR]]
- [[Run Syllable Spatial Heatmaps]]
- [[Run Info Dr Pause]]
- [[Prune Map]]
- [[NOR IMPRESS Index]]

#lava
