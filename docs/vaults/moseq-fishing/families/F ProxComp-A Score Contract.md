---
title: F ProxComp-A Score Contract
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
  - ProxComp-A Score Contract
  - Prox-stratified syllable composition contract
---
# F ProxComp-A Score Contract

**Declared:** 2026-10-06 (before peeking).  
**Status:** executed — lava on condition; assay litmus T1-assay pass ([[V ProxComp Null]] / [[Run ProxComp]]).  
**Parents:** [[H Investigation Quality]] (Q4 definition) · [[H Recognition Separators]] (recognition-linked separator hunt) · [[H Assay Validity NOR]] (Litmus T1-assay).  
**Claim kind on the I claims:** `#alphabet-bound` ([[Claim Kind]]). Prox gates are clock-portable; syllable richness / Shannon inside them are not.  
**Executed family note:** [[F ProxComp-A]]  
**Deferred grammar phase:** [[F ProxGram-A Score Contract]] — sealed after condition null.

> [!warning] Not classic DR
> This is **not** a rename of object-prox discrimination ratio (DR). Classic DR remains signed **time** near novel vs familiar. ProxComp scores are syllable **composition** inside exclusive fam / nvl balls, plus optional signed contrasts of those scalars.

---

## Plain ask

On recognition trials (`trial=nvl_obj`) across NOR sessions, with syllables filtered into exclusive 0.10 m object-prox masks:

1. **Panel (D):** what are richness / Shannon near familiar vs near novel?
2. **DR cousins (D → I):** do signed contrasts of those scalars behave like a preference / quality score?

---

## Design strip (locked)

| Axis | Lock |
|------|------|
| Cohort | IMPRESS NOR ladder `moseq_251017` (same 144-animal board as object_prox / NGramSeq) |
| Sessions | all present: `NOR_BL`, `NOR_TX`, `NOR_REC3hr`, `NOR_REC11hr` (cohort-dependent REC) |
| Trial | **`nvl_obj` only** |
| Prox masks | **r = 0.10 m**, **exclusive** fam vs nvl (dual-gated frames dropped; same exclusivity as `dr_exclusive`) |
| Bout gate | bout-mean distance to that object `< r` (object_prox convention) |
| Alphabet | **(1)** portable `cluster_id` first (primary lock / Family A); **(2)** then per-model `raw_syllable_id` as secondary board (separate INFO / companion BH if opened — do not pool with cluster Family A). ADR-0005: never headline raw ids across models as one alphabet |
| Unit | animal × session × trial × mask (panel); animal × session × trial (contrasts) |
| Representation | frame-share composition \(p\) inside each mask |
| Min-frame rule | **N = 10** (see § Where N applies) |
| Consensus | cluster board: one portable alphabet (no median-across-models). Per-model board: median across models of animal-level scalars **after** per-model mask filter (object_prox pattern) |
| Alternate spatial gate | **Preferred ROI redesign:** object-assigned arena **quadrants** + pooled `other` — [[F QuadComp-A Score Contract]] (own BH). This ProxComp board keeps **circular** 0.10 m for clock parity |

### Panel scalars (D — always emit; not in BH Family A)

| Token | Definition |
|-------|------------|
| `richness_fam_prox` / `richness_nvl_prox` | \(S\) = # categories with \(p_k > 0\) in that exclusive mask |
| `shannon_bits_fam_prox` / `shannon_bits_nvl_prox` | \(H(p)\) in bits on that mask |
| `hill2_eff` / `fam_hill2_prox` / `nvl_hill2_prox` | Hill q=2 effective number \(1/\sum p_k^2\) — **exploratory companion**; emit D; do **not** fold into Family A |
| `n_frames_fam_excl` / `n_frames_nvl_excl` | exclusive frame counts (observability) |

### DR-cousin scalars (D; I under declared litmus)

| Token | Formula |
|-------|---------|
| `delta_shannon_prox` | \(H_{\mathrm{nvl}} - H_{\mathrm{fam}}\) |
| `dr_shannon_prox` | \((H_{\mathrm{nvl}} - H_{\mathrm{fam}}) / (H_{\mathrm{nvl}} + H_{\mathrm{fam}})\) when denom \(> 0\); else NaN |
| `delta_richness_prox` | \(S_{\mathrm{nvl}} - S_{\mathrm{fam}}\) |
| `dr_richness_prox` | \((S_{\mathrm{nvl}} - S_{\mathrm{fam}}) / (S_{\mathrm{nvl}} + S_{\mathrm{fam}})\) when denom \(> 0\); else NaN |
| `dr_hill2_prox` | same DR form on `hill2_eff` — companion only; **not** Family A |

Sign convention matches classic DR: **+** = higher richness / Shannon / Hill2 **in the novel ball**.

### Where N applies (min-frame threshold)

**N = 10** is **not** the object-prox radius and **not** a bout-debounce. It is a **contrast eligibility** gate after masks are built:

```text
frames ──► exclusive 0.10 m fam / nvl masks (dual-gated dropped)
       ──► count n_frames_fam_excl, n_frames_nvl_excl
       ──► if either count < N: panel row may still emit (with counts);
            DR-cousin / delta scalars = NaN (excluded from Wilcoxon / Kruskal)
       ──► if both ≥ N: compute H, S, dr_*, delta_* on those frames
```

| Applies to | Does **not** apply to |
|------------|------------------------|
| Finite `dr_*_prox` / `delta_*_prox` for litmus T1-assay / T1 / sessΔ | Classic object-prox DR / `frac_near_*` (unchanged) |
| Both masks **jointly** (need ≥N on fam **and** ≥N on nvl) | Dropping raw frames from the H5 |
| Cluster board and per-model board the same way | Grammar / ProxGram (still sealed; will need its own transition budget) |

Report: n eligible vs n dropped per session × sex × condition. If drops are huge at N=10, raise N or treat as sparse-assay failure — do not impute.

---

## Litmus cascade (must run in order)

See [[Litmus Ladder]]. Old letters A/B/C = T1-assay / T1 / sessΔ.

### Litmus T1-assay — Assay validity (composition preference in controls)

**Grain:** `NOR_TX` × `nvl_obj`.  
**Stratum:** `condition=noSD` primary; companion sex=all pooled OK as D only.  
**Tests (uncorrected, planned):** Wilcoxon signed-rank vs 0 on `dr_shannon_prox` and on `dr_richness_prox` (within sex if n allows).  
**Pass language:** controls show novel-ball composition asymmetry (median DR-cousin > 0, Wilcoxon hit).  
**Fail:** do **not** sell ProxComp as a recognition readout; may still report panel D across sessions as protocol description only.

### Litmus T1 — Condition separation at challenge

**Only if T1-assay does not kill the score.**  
**Family [[F ProxComp-A]]:** Kruskal–Wallis on `condition` within sex for **two** primary contrasts:

| Metric | Sex | Cells |
|--------|-----|-------|
| `dr_shannon_prox` | F, M | 2 |
| `dr_richness_prox` | F, M | 2 |

**m = 4.** Hit rule: `hit_fdr05` ⇔ `q_bh < 0.05` within this family only.  
**Not in Family A:** panel levels, `delta_*` (report as companion D/I outside BH), REC sessions, grammar.

**Level mismatch fix:** absolute `fam_*` / `nvl_*` shannon–richness levels are **not** in ProxComp-A. Confirmatory BH after peek → [[F ProxLevel-A]] (m=8; executed lava — see [[V ProxComp Null]]).

### Litmus sessΔ — Session dynamics (after T1-assay; independent of T1)

Paired within-animal Δ of `dr_shannon_prox` / `dr_richness_prox` on steps BL→TX, TX→REC*, BL→REC* (declare steps in Run INFO).  
D story first (median Δ, frac>0). Optional: Kruskal on Δ by `condition` = difference-of-differences — **separate** BH family if opened (`F ProxComp-SessDelta`); do not fold into Family A.

---

## Explicitly out of scope (this contract)

| Item | Why |
|------|-----|
| Classic `dr_exclusive` re-cut | Already answered ([[H Novelty Preference DR]]) |
| Whole-trial Shannon / richness @ `nvl_obj` | Shelf companion; not prox-stratified ([[Prune Map]]) |
| Fixed-budget pair MI / bigram @ full `nvl_obj` | Failed ([[V NGramSeq Null]]); different grain |
| Bout \(H(\mathrm{next}\mid\mathrm{current})\) / TV / n-grams **inside** masks | [[F ProxGram-A Score Contract]] only after A |
| Arena side / quadrant composition | [[F QuadComp-A Score Contract]] — alternate gate, own BH |
| Clock-portable side-mass occupancy | Already fail ([[V Side Geometry Null]]); QuadComp is **syllable** composition in sides, not `frac_nvl_side` redo |
| Physio Spearman | [[H Physio Coupling]] waits for a locked behavior metric |

---

## Honesty language (pre-register)

> Prox-stratified syllable composition (exclusive 0.10 m fam vs nvl masks on `nvl_obj`) is a **new** recognition-linked score family. Panel richness / Shannon are D. Signed `dr_*_prox` cousins are preference-of-**repertoire**, not preference-of-**time**. Condition claims require Family A FDR. Grammar stays sealed until composition Litmus T1-assay is decided.

---

## Related

- [[F ProxComp-A]] · [[F ProxGram-A Score Contract]] · [[F QuadComp-A Score Contract]]
- [[H Investigation Quality]] · [[H Recognition Separators]] · [[H Assay Validity NOR]]
- [[Run Object Prox DR]] (gate definition) · [[Run Nearest Prox MI]] (distinct MI claim; already null on condition)
- [[V Side Geometry Null]] — occupancy geometry null; not a substitute for QuadComp
- [[V NGramSeq Null]] · [[V TransStruct Null]] · [[V Visit Grammar Null]] — cousins, not substitutes
