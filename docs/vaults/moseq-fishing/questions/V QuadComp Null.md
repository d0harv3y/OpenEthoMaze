---
title: V QuadComp Null
type: verdict
assay: nor-impress
status: lava
claim_kind: alphabet-bound
verdict: fail
tags:
  - claim/verdict
  - assay/nor-impress
  - lava
  - alphabet-bound
aliases:
  - Q5 QuadComp Honesty Pass
---
# V QuadComp Null

**Date:** 2026-10-06  
**Scope:** [[F QuadComp-A]] / [[F QuadLevel-A]] / [[Run QuadComp]] (DR family declared in [[F QuadComp-A Score Contract]] before peeking; Level family confirmatory after peek).  
**Gate:** Kruskal on DR cousins (m=4) and on fam/nvl levels (m=8) by `condition` within sex at `NOR_TX` × `nvl_obj`; `hit_fdr05` within each BH family separately.  
**Claim kind:** #alphabet-bound

## Verdict

**Family A fail** (condition) on DR cousins **and** absolute levels. **Litmus T1-assay pass** (assay validity in `noSD`).

QuadComp-A: zero `hit_fdr05`, zero uncorrected `hit_p05`. Best cell: F `dr_shannon_quad` (p≈0.072 → q≈0.202).  
QuadLevel-A: zero FDR / zero uncorrected; closest F `fam_richness_quad` p≈0.053.

Do **not** invent Family B on the same quadrant ROI without user OK. Circular ProxComp sibling remains available ([[F ProxComp-A Score Contract]] / [[F ProxLevel-A]]). Grammar ([[F ProxGram-A Score Contract]]) stays sealed — composition condition null does not unlock grammar fishing.

## Litmus T1-assay (assay)

### DR cousins (Family A metrics)

| Cell                   | n   | median | p       | hit |
| ---------------------- | --- | ------ | ------- | --- |
| all `dr_shannon_quad`  | 45  | 0.072  | 0.016   | yes |
| all `dr_richness_quad` | 45  | 0.111  | 0.00057 | yes |
| F `dr_richness_quad`   | 23  | 0.176  | 0.00045 | yes |
| F/M shannon within sex | —   | +      | >0.05   | no  |
| M richness             | 22  | 0.053  | 0.28    | no  |

### Constituents (`fam_*` / `nvl_*`; paired Wilcoxon nvl−fam in `noSD`)

Panel D tokens (also alias `shannon_bits_*_quad` / `richness_*_quad`). **Not** in QuadComp-A BH.

| Kind | sex | n | med fam | med nvl | Δ (nvl−fam) | p | hit |
|------|-----|---|---------|---------|-------------|---|-----|
| shannon | all | 45 | 2.16 | 2.32 | +0.16 | 0.027 | yes |
| shannon | F | 23 | 2.16 | 2.76 | +0.60 | 0.061 | no |
| shannon | M | 22 | 2.14 | 2.20 | +0.05 | 0.23 | no |
| richness | all | 45 | 8 | 10 | +2 | 0.00019 | yes |
| richness | F | 23 | 8 | 11 | +3 | 0.00027 | yes |
| richness | M | 22 | 8.5 | 9 | +0.5 | 0.26 | no |

Controls prefer novel-quadrant **repertoire** (sex=all on DR and on level Δ). That is not classic time DR, but it is a recognition-linked composition asymmetry.

### Level × condition — [[F QuadLevel-A]] (confirmatory BH after peek)

Mismatch fix: Family A was DR-cousins only; constituents needed their own litmus-B family. User-authorized 2026-10-06; **not** a pre-peek blind lock.

| Cell | p | q_bh |
|------|---|------|
| F `fam_shannon_quad` | 0.070 | 0.281 |
| M `fam_shannon_quad` | 0.559 | 0.894 |
| F `nvl_shannon_quad` | 0.820 | 0.937 |
| M `nvl_shannon_quad` | 0.769 | 0.937 |
| F `fam_richness_quad` | 0.053 | 0.281 |
| M `fam_richness_quad` | 0.232 | 0.499 |
| F `nvl_richness_quad` | 0.979 | 0.979 |
| M `nvl_richness_quad` | 0.250 | 0.499 |

**0/8** `hit_fdr05`; **0/8** `hit_p05`. Same pattern as QuadComp-A: T1-assay holds; T1 condition does not.

## Locked negative language (condition)

> Object-assigned quadrant syllable composition contrasts (`dr_shannon_quad`, `dr_richness_quad` on exclusive `fam_quad` vs `nvl_quad`, portable `cluster_id`, N=10) do **not** separate `noSD` / `GHSD` / `RBSD` under QuadComp-A (0/4 `hit_fdr05`; 0/4 uncorrected). Absolute fam/nvl Shannon–richness levels under QuadLevel-A likewise fail (0/8 FDR; 0/8 uncorrected). Assay-validity Wilcoxon vs 0 in `noSD` at `NOR_TX` **passes** for sex=all on both DR cousins; constituent medians show higher `nvl_shannon_quad` / `nvl_richness_quad` than fam (sex=all).

## Evidence

| Artifact | Finding |
|----------|---------|
| `quad_comp_tests_long.csv` | 4/4 finite p; **0** `hit_fdr05`; **0** `hit_p05` |
| `quad_level_tests_long.csv` | 8/8 finite p; **0** `hit_fdr05`; **0** `hit_p05` |
| `quad_comp_litmus_t1_assay.csv` (on disk also `quad_comp_litmus_a.csv`) | 3/6 `hit_p05` (both sex=all + F richness) |
| `quad_comp_per_animal.csv` | 432 rows; TX eligible n≈139 animals; 0 collisions @ TX |
| `run_summary.json` | `litmus_t1_assay_pass: true` (legacy `litmus_a_pass`); `pass_family_a: false`; `pass_level_family_a: false` |

Full paths → [[Run QuadComp]].

## Related

- [[F QuadComp-A Score Contract]] · [[F QuadComp-A]] · [[F QuadLevel-A]] · [[Run QuadComp]]
- [[V Prox Quad SessDelta Null]] — Litmus sessΔ
- [[H Investigation Quality]] · [[H Recognition Separators]] · [[H Assay Validity NOR]]
- [[V Side Geometry Null]] · [[H Novelty Preference DR]]
