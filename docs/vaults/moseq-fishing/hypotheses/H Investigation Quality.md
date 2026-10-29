---
title: H Investigation Quality
type: hypothesis
assay: nor-impress
status: rabbit-hole
claim_kind: na
verdict: fail
tags:
  - claim/hypothesis
  - assay/nor-impress
  - rabbit-hole
aliases:
  - Q4 Investigation Quality
---
# H Investigation Quality

**Parent:** [[T4 Measurement Quality]].
**Status:** audited shelf + Prox/Quad line **fail** condition litmus; assay litmus (T1-assay) passes on new scores. #rabbit-hole

---

**Question:** Is there a syllable- (or bout-) based **investigation quality** score that adds something DR does not — and that separates condition or tracks physio?

**Status:** Prox/Quad composition + time twins **do not** separate condition ([[V ProxComp Null]], [[V QuadComp Null]]). Assay asymmetry in controls **does** pass. Grammar remains sealed.

**Must not be:** DR in disguise; total locomotion; raw `raw_syllable_id` across models (ADR-0005).

**Audited (2026-09-23) — none lock:**

| Candidate                                                                           | Result                                    |
| ----------------------------------------------------------------------------------- | ----------------------------------------- |
| Classic `t_nvl_s` / `t_fam_s` / locomotor confounds @ `NOR_TX` (declared BH family) | **0** FDR                                 |
| Four-mask TX−BL×condition on `nvl_obj` (INFO family)                                | **0** FDR                                 |
| DR×pause INFO / nearest-prox MI                                                     | FDR miss ([[V Recognition Lattice Null]]) |

**Still need new definition (not on shelf):**

- ~~Bout duration / approach–leave grammar near novel~~ — computed; **fail** ([[V Visit Grammar Null]])
- ~~Per-animal quadrant / side-mass~~ — computed; **fail** ([[V Side Geometry Null]])
- Residual of DR after regressing locomotor confounds — only if residual separates condition
- ~~**Prox-stratified syllable composition**~~ — computed: Litmus T1-assay **pass** (DR + `fam_*`/`nvl_*` shannon–richness); ProxComp-A / TimeProx-A **fail** ([[V ProxComp Null]] / [[Run ProxComp]]); per-scalar BH redo (shannon / richness / hill2 each m=2) also condition **fail** ([[V ProxComp Per-Scalar Null]] / [[Run ProxComp Per-Scalar]])
- ~~**Quadrant ROI composition**~~ — Litmus T1-assay **pass** (DR + constituents); QuadComp-A / TimeQuad-A **fail** ([[V QuadComp Null]] / [[Run QuadComp]]); `dr_time_quad` same pattern
- ~~Session paired Δ (Litmus sessΔ)~~ — Wilcoxon dynamics hits (incl. level Δ); Δ×condition **0 FDR** ([[V Prox Quad SessDelta Null]] / [[Run Prox Quad Session Delta]])
- ~~Per-model alphabet board~~ — exploratory raw×21: consensus **fail**; 1/21 lone Quad FDR not promoted ([[V Prox Quad Per Model Null]] / [[Run Prox Quad Per Model]])
- Grammar sealed — [[F ProxGram-A Score Contract]]

**Litmus before claiming per-animal kpMS *helps* quality:** score correlates with classic investigation or DR residual in `noSD`, and/or separates condition, and/or survives physio FDR gate in [[H Physio Coupling]]. Accent remapping bearings exist without that lock ([[H Alphabet Equating]]) — do not confuse the two.

**ProxComp litmus order (locked 2026-10-06; [[Litmus Ladder]]):** (T1-assay) assay validity — Wilcoxon vs 0 on `dr_shannon_prox` / `dr_richness_prox` in `noSD` @ `NOR_TX`; (T1) Kruskal×condition Family A (4 cells); (sessΔ) session paired Δ. Composition before grammar.

## Artifacts (exploratory joins)

- [[Run QuadComp]] · [[Run ProxComp]] · [[Run ProxComp Per-Scalar]] · [[Run Prox Quad Session Delta]] · [[Run Prox Quad Per Model]] · [[Run DR Framed Deck Exemplar]]
- [[V QuadComp Null]] · [[V ProxComp Null]] · [[V ProxComp Per-Scalar Null]] · [[V Prox Quad SessDelta Null]] · [[V Prox Quad Per Model Null]]
- [[F ProxComp-A Score Contract]] / [[F ProxComp-A]] · [[F ProxComp Per-Scalar Score Contract]] / [[F ProxComp Per-Scalar]] · [[F QuadComp-A Score Contract]] / [[F QuadComp-A]]
- [[F ProxGram-A Score Contract]] — sealed (composition condition null; do not open)
- [[Run Info Dr Pause]]
- [[Run Nearest Prox MI]]
- [[Run Syllable Signatures]]
- [[Run Syllable Kinematics]]
- Four-mask TX−BL negative — see [[V Candidate Lattice Null]] (no dedicated Run hub yet; folder demoted on [[Prune Map]])
- [[Run Bout Grammar]] — visit grammar; FDR fail
- [[V Candidate Lattice Null]]
- [[V Visit Grammar Null]]
- [[H Alphabet Equating]] / [[Run Per Animal Paramscan]] — segmentation remapping, not a quality lock

## Related

- [[H Recognition Separators]]
- [[H Physio Coupling]]
- [[H Alphabet Equating]]
- [[NOR IMPRESS Index]]
