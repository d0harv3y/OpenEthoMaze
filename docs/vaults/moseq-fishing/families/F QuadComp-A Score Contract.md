---
title: F QuadComp-A Score Contract
type: family
assay: nor-impress
status: open
claim_kind: na
verdict: na
tags:
  - claim/family
  - assay/nor-impress
  - open
aliases:
  - QuadComp-A Score Contract
  - Quadrant-stratified syllable composition contract
---
# F QuadComp-A Score Contract

**Executed family note:** [[F QuadComp-A]]  
**Verdict:** [[V QuadComp Null]] — Litmus T1-assay pass; Family A condition fail (0/4 FDR).  
**Run:** [[Run QuadComp]]

**Declared:** 2026-10-06 (before peeking; geometry revised same day).  
**Status:** executed — lava on condition; assay litmus kept.  
**Parents:** [[H Investigation Quality]] · [[H Recognition Separators]].  
**Claim kind:** `#alphabet-bound` for syllable panel / `dr_*_quad`. Optional time twin is `#clock-portable` (see § Clock-portable companion).  
**Sibling:** [[F ProxComp-A Score Contract]] keeps the **circular** object-ball gate for sensitivity / clock parity with classic DR — separate BH; do not pool.

> [!warning] Not SideMass / not circular prox
> [[V Side Geometry Null]] failed **half-arena occupancy** (`frac_nvl_side`). This contract uses **object-assigned quadrants** (¼-arena ROIs) and asks about **syllable repertoire** (and optionally time) inside them — not midline mass, not r = 0.10 m disks.

> [!info] Prior on hits
> Lab prior on condition FDR hits is **low** (SideMass null; classic DR×condition null; whole-trial Shannon/NGramSeq nulls). Still worth a clean litmus: assay-validity (T1-assay) may pass while condition (T1) fails — that is an honest outcome, not a fishing license.

---

## Plain ask

On `nvl_obj`, treat each object’s ROI as the **arena quadrant containing that object’s center**. Summarize syllable richness / Shannon in `fam_quad` vs `nvl_quad`; remaining area is one pooled stratum `other` (for later contrast only). Same cascade T1-assay → T1 → sessΔ; composition before grammar.

---

## Geometry (locked)

The spatial heatmaps show the two objects on a **diagonal** after fam-left alignment (example: `syllable_spatial_heatmaps` on `nvl_obj`). The object centers do **not** share a similar y. Do **not** talk about left/right halves for this score.

| Step | Lock |
|------|------|
| Alignment | Same fam-left rot180 as [[Run Side Mass]] / spatial heatmaps (for overlay parity only) |
| Center | Arena center from the NOR H5 |
| Four cells | Split the arena into four equal parts about the center |
| Name the parts | **`fam_quad`**, **`nvl_quad`**, **`other`** — not NW/NE/SW/SE in claim language |
| Assign | `fam_quad` = the one cell that holds the familiar object center; `nvl_quad` = the one cell that holds the novel object center |
| `other` | The other two cells as **one** stratum (usual case under diagonal placement) |
| Collision | Same cell for both centers → NaN contrasts; count and report |

**Direction is not part of the claim.** Compass labels may appear in code or QC plots. The science tokens stay `fam_quad` / `nvl_quad` / `other`.

```text
After alignment (typical diagonal):

        ┌──────────┬──────────┐
        │  other   │ nvl_quad │
        ├──────────┼──────────┤
        │ fam_quad │  other   │
        └──────────┴──────────┘

(or the opposite diagonal — still fam_quad / nvl_quad / other)
```

**Not this gate:** circular disk of radius r about the object center ([[F ProxComp-A Score Contract]]).
**Not this gate:** half-arena `frac_nvl_side` ([[V Side Geometry Null]]).

---

## Design strip

| Axis | Lock |
|------|------|
| Cohort / sessions / trial | `moseq_251017`; all sessions; **`nvl_obj` only** |
| Alphabet | **`cluster_id` first**; then per-model secondary board (own BH if opened) |
| Panel strata (D) | `fam_quad`, `nvl_quad`, `other` — richness + Shannon + Hill q=2 (`hill2_eff`) + frame counts each |
| Primary DR cousins | `dr_shannon_quad`, `dr_richness_quad` on **nvl_quad vs fam_quad** only (same formulas as ProxComp; + = higher in novel quadrant) |
| Companion DR | `dr_hill2_quad` — exploratory; **not** Family A (see [[Run Prox Quad Comp Figs]]) |
| Min-frame N | **N = 10** on **both** `fam_quad` and `nvl_quad` for finite primary contrasts (same eligibility semantics as ProxComp § Where N applies) |
| `other` contrasts | **sealed for Family A** — emit D panel; optional later family (e.g. object-union vs `other`) only with user OK after peeking is forbidden |
| Family A (Litmus T1) | Kruskal on `dr_shannon_quad` / `dr_richness_quad` × F/M → **m = 4**; **separate** from ProxComp-A |
| Level family (Litmus T1 on constituents) | [[F QuadLevel-A]]: Kruskal on `fam_*`/`nvl_*` shannon+richness × F/M → **m = 8**; confirmatory BH after peek (2026-10-06); **separate** from QuadComp-A |

### Litmus cascade

Same as ProxComp ([[Litmus Ladder]]): **T1-assay** Wilcoxon vs 0 in `noSD` @ `NOR_TX` → **T1** Family A condition → **sessΔ** session paired Δ. Grammar sealed ([[F ProxGram-A Score Contract]] analog for quads — do not open until T1-assay decided). Constituent levels get their own T1 board ([[F QuadLevel-A]]), not folded into QuadComp-A.

---

## Clock-portable companion (optional; not Family A)

If you want the **same ROI change for time-preference** (true DR redesign, not syllable):

| Token | Formula |
|-------|---------|
| `dr_time_quad` | \((T_{\mathrm{nvl\_quad}} - T_{\mathrm{fam\_quad}}) / (T_{\mathrm{nvl\_quad}} + T_{\mathrm{fam\_quad}})\) |

Exclusive: frames in `other` and dual-object-quad (impossible if distinct cells) do not enter the denom. This is **closer to classic DR** than SideMass half-share, but still a large ROI → expect high correlation with `frac_nvl_side` / classic DR and **low** odds of new condition separation. Declare a **separate** small family if tested; do not fold into QuadComp-A syllable BH.

---

## Order vs ProxComp

| Board | ROI | Role |
|-------|-----|------|
| **QuadComp (this)** | object-assigned **quadrants** + `other` | **Primary** spatial redesign for composition DR-cousins |
| ProxComp | exclusive **0.10 m** disks | Sensitivity / parity with locked object_prox clock |

Run QuadComp first if compute is sequenced; ProxComp remains pre-registered sibling, not abandoned.

---

## Related

- [[F ProxComp-A Score Contract]] · [[F ProxComp-A]] · [[F ProxGram-A Score Contract]]
- [[E Side Geometry]] · [[Run Side Mass]] · [[V Side Geometry Null]]
- [[H Investigation Quality]] · [[H Recognition Separators]] · [[H Novelty Preference DR]]
