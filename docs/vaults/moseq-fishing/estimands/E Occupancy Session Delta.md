---
title: E Occupancy Session Delta
type: estimand
assay: nor-impress
status: open
claim_kind: na
verdict: fail
tags:
  - claim/estimand
  - assay/nor-impress
  - open
aliases:
  - Q5 Occupancy Session-Delta Score Contract
---
# E Occupancy Session Delta

**Date:** 2026-09-23  
**Status:** declared → **computed** → [[V Occupancy Delta Null]] **fail** (0/4 `hit_fdr05`).  
**Parent:** [[H Recognition Separators]]  
**Run:** [[Run Occupancy Session Delta]]

## One-line

Within-animal **BL→TX** change in object-prox occupancy (`frac_near_nvl` / `frac_near_fam`) — does `condition` modulate that rise? Not DR; not engagement Δ (`no_obj→id/nvl`); not TX **level** Family A ([[V Candidate Lattice Null]]).

## Score definitions

Upstream: [[Run Object Prox DR]] — per model `frac_near_*`, then **median across models** per animal × session (same consensus grain as Candidates occupancy).

$$
\Delta\mathrm{frac\_near\_nvl} = \mathrm{frac\_near\_nvl}(\mathrm{NOR\_TX}) - \mathrm{frac\_near\_nvl}(\mathrm{NOR\_BL})
$$

Same for `frac_near_fam`. Trial = `nvl_obj`; r = 0.10 m.

## Grain / design

- Grain: `animal × (BL→TX) × nvl_obj`  
- Association: paired first difference, then independent-groups Kruskal on Δ by `condition` within sex  
- **Not** four_mask TX−BL ANOVA on syllable masks; **not** TX-level occupancy family

## BH Family OccSessDelta-A (locked)

| Axis | Levels |
|------|--------|
| session_step | `BL→TX` only |
| metric | `delta_frac_near_nvl`, `delta_frac_near_fam` |
| sex | F, M |

**Family size:** 1 × 2 × 2 = **4** Kruskal cells.  
**Hit rule:** `hit_fdr05` ⇔ `q_bh < 0.05` within this family.  
**Pass / fail:** ≥1 FDR hit vs stop; no Family B without user OK.

## Peek caveat (honesty)

Uncorrected Kruskal p on `delta_frac_near_nvl` was inspected in chat **before** this contract was written (F≈0.074, M≈0.034). This family is therefore **confirmatory BH** on a named 4-cell set after an exploratory peek — not a blind pre-registration. Claim gate remains `q_bh`, not those p values.

## Related

- [[V Candidate Lattice Null]] — TX **level** occupancy BH fail  
- [[V Recognition Lattice Null]]  
- [[Run Object Prox DR]]  
- [[NOR IMPRESS Index]]
