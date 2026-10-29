---
title: Motion Sequencing DR Framed Report
type: report
assay: nor-impress
status: ladder
claim_kind: mixed
verdict: na
tags:
  - claim/report
  - assay/nor-impress
  - ladder
  - mixed
---
# Motion Sequencing DR Framed Report

**Status:** synthesis (2026-10-09). Lab-internal **6-slide** spine reframing **novel object recognition (NOR)** + sleep-deprivation (**SD**) motion sequencing through **discrimination ratio (DR)** and fam|nvl constituents (keypoint-MoSeq / **kpMS**). Sibling to [[Motion Sequencing Honest Report]]; denser DR/prox focus, less sequence-null inventory.

**Mini-poster:** `C:\Users\admin\Documents\work\davis lab\Motion sequencing NOR - DR framed.pptx` (figures embedded as **SVG** for Convert to Shape / Object)  
**Join-board run:** [[Run DR Framed Deck Exemplar]]  
**Exemplar alphabet:** `paramscan_s1-1e7_s2-3e4_ss-100` `raw_syllable_id` (pause syll = **5**). Consensus = light prose only.

**Claim kinds:** [[Claim Kind]] — `#clock-portable` vs `#alphabet-bound`.

---

## Acronyms

NOR = novel object recognition; SD = sleep deprivation; kpMS = keypoint-MoSeq; DR = discrimination ratio; ProxComp = proximity composition (0.10 m exclusive balls); BH = Benjamini–Hochberg; FDR = false discovery rate; SSL = self-supervised learning.

---

## Slide spine (PPT claims)

| # | Title | Headline |
|---|--------|----------|
| 1 | Assay prefers novel — clocks agree | Preference at `NOR_TX` on classic / object-prox; SD arms do not separate. Panels: classic DR · classic↔object-prox · `frac_still`↔pause syll5 (condition color / sex marker). (`dr_time_prox` join = board A on disk, not on PPT.) |
| 1b | Composition ladder (COUNT / UNCERTAINTY) | PPT table: `richness` / `shannon_bits` / `hill2_eff` formulas from `docs/vocab/FORMULAS.md` (no conditional entropy). Bridge into composition-DR slides. |
| 2 | Composition DR cousins | Richness → Shannon → Hill q=2 ask repertoire / uncertainty / effective motifs. Assay litmus pass; condition FDR fail under **sex-stratified** per-scalar BH (and sealed m=2) — [[V ProxComp Per-Scalar Null]]. Violin footnotes: min BH q + grain. |
| 3 | Session steps | BL→TX→REC Δs (no trial-steps). Panels L→R richness / Shannon / Hill2 (match slide 2); sex-strat BH within sex; min-q footnotes. Protocol dynamics ≠ condition modulation. (`frac_near` twin = vault G only.) |
| 4 | Can / cannot | Can: assay, clock concordance, control composition preference. Cannot: recognition-linked SD lock; clinical meaning of composition-DR unknown. Figs L→R classic↔richness / Shannon / Hill2 (condition color / sex marker). |
| 5 | Future | Preface: residual litmus is a sealed null — do not lead with formula walls (`resid_*` = leftover after declared covariates, not a new clock). Next: different clocks; B-SOiD; SSL video embeddings (leJEPA / DINO / SimCLR) that skip pose/kpMS as middleman (video → keypoints → syllables → behavior) in favor of pixel/clip embeddings → ethogram — `C:\Users\admin\code\lightly`. |

PPT has **no** vault wikilinks or levity tags.

---

## Results (computed joins)

Grain for A/D: animal × `NOR_TX` × `nvl_obj` (eligible). Source arts: [[Run DR Framed Deck Exemplar]].

| Board | Pair | n | Spearman ρ | hit_p05 | Kind |
|-------|------|---|------------|---------|------|
| A | classic ↔ `dr_time_prox` | 139 | 0.937 | yes | #clock-portable |
| B | classic ↔ object-prox DR | reuse [[Run Classic DR]] | — | — | #clock-portable |
| C | `frac_still` ↔ syll5 share (ladder) | 1296 | 0.804 | yes | #alphabet-bound (syll id) / clock twin |
| C | same @ `NOR_TX` × `nvl_obj` | 144 | 0.719 | yes | same |
| D | classic ↔ `dr_richness_prox` | 139 | 0.727 | yes | #alphabet-bound |
| D | classic ↔ `dr_shannon_prox` | 139 | 0.079 | no | #alphabet-bound |
| D | classic ↔ `dr_hill2_prox` | 139 | −0.083 | no | #alphabet-bound |

**Read:** Time clocks are nearly interchangeable with classic investigation DR. Richness DR still tracks time mass; Shannon / Hill2 do **not** — they are asking a different question (repertoire shape), which is why they belong on slide 2 without stealing the assay headline.

**E / F:** Exemplar ProxComp level + session-step violins/Kruskal for shannon / richness / hill2 under `simpler_first_dr_framed_deck_exemplar/`. Deck figures use **sex-stratified BH** (not the sealed m=2 F+M bag); footnotes report min q + grain. Still **0 FDR hits** @ 0.05 — closest miss session-step richness q≈0.063. Twin **G** (`frac_near`) vault-only. Details: [[Run DR Framed Deck Exemplar]].

---

## Conclusions

**We can say:**

1. Assay novelty preference holds at recognition; SD does not separate classic DR here.
2. Clock concordance (classic / object-prox / `dr_time_prox`; still / pause syll5) is expected V&V under collinearity.
3. Composition DR cousins pass assay litmus in controls and fail condition under declared per-scalar BH families.

**We cannot say:**

1. These scalars lock a recognition-linked SD impairment.
2. Composition-DR has known clinical meaning (show, don't sell).
3. Shannon / Hill2 are interchangeable with investigation-time DR (they aren't — board D).

---

## Related

- [[Run DR Framed Deck Exemplar]] · [[Run ProxComp Per-Scalar]] · [[Run Classic DR]] · [[Run Session Paired]] · [[Run Object Prox DR]]
- [[V ProxComp Per-Scalar Null]] · [[V ProxComp Null]] · [[H Investigation Quality]] · [[H Assay Validity NOR]]
- [[Motion Sequencing Honest Report]] · [[NOR IMPRESS Index]] · [[Campaign Roots]]

**Regen PPTX** (PowerShell COM):

```powershell
powershell -File scratch/nor_object_mi/build_dr_framed_motion_seq_deck.ps1
```
