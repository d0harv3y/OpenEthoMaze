---
title: Motion Sequencing Honest Report
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
# Motion Sequencing Honest Report

**Status:** synthesis (2026-10-05). Human-facing claim spine for what **keypoint-MoSeq (kpMS)** can honestly say in IMPRESS **novel object recognition (NOR)** with sleep-deprivation (**SD**) arms. Not a manuscript Methods section; not a recompute.

**Thesis:** Latent pose segmentation largely **reproduces** the classic movement / proximity clock (instrument check). Composition decks rediscover protocol dynamics without locking a recognition-linked SD separator. The place syllables *could* add beyond thresholding — **sequence structure** (transitions / n-grams) — was honesty-gated and is a **clean null** so far. Residual litmus after Layer A regression is also **null** — syllable scores are redundant for condition beyond speed / immobile / `frac_near`.

**Mini-poster:** `C:\Users\admin\Documents\work\davis lab\Motion sequencing in NOR - honest report.pptx` (sibling to the 60-slide hunt deck).

**Claim kinds:** [[Claim Kind]] — `#clock-portable` vs `#alphabet-bound`. Figures: [[Artifact Linking]] § Figures.

---

## Acronyms

NOR = novel object recognition; SD = sleep deprivation; kpMS = keypoint-MoSeq; DR = discrimination ratio; DA = differential abundance; FDR = false discovery rate; BH = Benjamini–Hochberg; V&V = verification and validation.

---

## Thin NOR + SD context (not this report’s job)

Full claim map: [[NOR IMPRESS Index]]. Vocab overview: `docs/vocab/NOR-IMPRESS-OVERVIEW.md`.

| Fact | Honest read | Home | Kind |
|------|-------------|------|------|
| Assay works at challenge | Controls / pooled prefer novel on `nvl_obj` at `NOR_TX` | [[H Assay Validity NOR]] | #clock-portable |
| DR × condition | **Null** at `NOR_TX` — SD arms do not shift classic preference on this DR | [[H Novelty Preference DR]] | #clock-portable |
| Engagement Δ (M) | Object-appearance `frac_near` rise separates arms — **occupancy**, not MoSeq insight | [[V Engagement Delta]] | #clock-portable |

Do **not** read the sequencing story as “SD broke memory.” Preference did not move; MoSeq composition did not invent that headline either.

---

## Results

### 1. Layer A — expected concordance (V&V, not insight) #clock-portable

**Claim:** kpMS segmentation with latent pose modeling effectively reproduces much of what classic **threshold + debounce** (and object-prox gates) already measure.

| Concordance | Read |
|-------------|------|
| Object-prox DR ↔ syllable-prox DR | Preference / near-object time clocks agree across segmenters |
| Time still / `frac_still` ↔ pause cluster (`cluster_id` 13 on the 251017 slides pack) | Immobility mass aligns with the “pause” kinematic prototype — **fit-local id** (ADR-0005) |

**Artifacts / figures:** [[Run Syll Ambulation Overlap]] (locomotor concordance SVGs + ambulation-clock PNGs) · [[Run Slides Pack]] (`frac_still/`, `cluster13/`) · [[Run Object Prox DR]] (DR / occupancy panels).

**Why this should be expected:** Debounce / speed / immobile / `frac_near` answer *where and how much* the animal moves (and near objects). Syllables answer *which reusable pose motifs* and *in what order*. Using MoSeq as a fancier occupancy / Shannon / Bray–Curtis machine rediscovers the same engagement clock Layer A already checked — **collinearity**, not a mysterious MoSeq failure. That is useful **V&V**; it does **not** answer memory or physio.

### 2. Composition / inventory — rediscovery, no recognition lock #alphabet-bound

**Claim:** Syllable composition, richness, Shannon, DA, and cluster frame-share chart **task-state / protocol dynamics** (BL→TX→REC; object-appearance steps). They do **not** lock a recognition-linked condition separator.

**Sell carefully:** Session shifts and thin condition×cluster cells are easy to oversell as “memory.” They are Layer B under [[H Syllable Task State]] — real and charted; **not** preference and **not** physio unless joined under a declared Layer C score.

**Honesty cards (vaulted):** [[V Composition Step Fishing]] (DA / Shannon / BC / cluster fishing) · [[V Protocol Step Clocks]] (threshold-reachable trial/session steps + [[F Stillness-Companion-A]] pass) · thin keep [[V Composition Companion Partial]].

**Artifacts / figures:** [[Run Session Paired]], [[Run Presence Steps]], [[Run Simpler First DA]], [[Run Slides Pack]] (`shannon/` etc.). Honesty posture: [[V Engagement Delta]], [[V Recognition Lattice Null]], [[Prune Map]] § `slides_pack/`.

### 3. Sequence structure — fairly tested, clean null #alphabet-bound

**Claim:** The one place syllables can ask what pose debounce **cannot** — bout **transition** / **n-gram** structure at recognition — was pre-declared and **failed**.

| Family | Verdict | Note |
|--------|---------|------|
| TransStruct-A (TV to noSD ref + H(next\|current) @ `NOR_TX` × `nvl_obj`) | **Fail** — 0/4 FDR, 0/4 uncorrected | [[V TransStruct Null]] |
| TransStruct-B (6 expanded grains incl. full `NOR_TX` session) | **Fail** — 0/24 FDR | [[V TransStruct Expanded Null]] |
| NGramSeq-B (same 6 grains) | **Fail** — 0/24 FDR | [[V NGramSeq Expanded Null]] |
| TransStruct-C (all 12 level grains) | **Fail** — 0/48 FDR | [[V TransStruct Full Grid Null]] |
| NGramSeq-C (all 12 level grains) | **Fail** — 0/48 FDR | [[V NGramSeq Full Grid Null]] |
| Cross-campaign TransStruct | Null where clean; TV hits that vanish under fixed budgets = **snake** | [[V TransStruct Cross-Campaign]] |
| NGramSeq-A @ `nvl_obj` | **Fail** — 0/4 FDR | [[V NGramSeq Null]] |
| Residual-A | **Fail** — 0/6 FDR | [[V Residual Litmus Null]] |
| TransStruct / NGramSeq **PerGrain** (m=4 each grain) | **Fail** — 0/12 grains each | [[V TransStruct PerGrain Null]] · [[V NGramSeq PerGrain Null]] |
| Composition companions | **Partial** — not recognition lock | [[V Composition Companion Partial]] |
| Stillness companion (`frac_still` REC3 × `no_obj`) | **Pass** 2/2 — clock twin of Shannon Companion-B | [[F Stillness-Companion-A]] / [[V Protocol Step Clocks]] |

Do **not** invent Family B on these scalars without a new contract + user OK. Locked negative language lives on the verdict notes — do not paraphrase into a softer claim. Few dedicated figures for sequence families — tables on the Runs are enough. Joint vs per-grain: [[Joint vs Per-Grain FDR]].

---

## Conclusions

**We can honestly say:**

1. **Instrument check passed** (#clock-portable). kpMS reproduces the classic movement / proximity / stillness clock (DR concordance; still ↔ pause cluster). Expected under collinearity with Layer A.
2. **Composition is not a MoSeq preference claim** (#alphabet-bound). Shannon / DA / cluster decks support protocol-story slides; they do not lock SD impairment of novel preference.
3. **Sequence + residual bets lost so far** (#alphabet-bound). Transitions, fixed-budget n-grams, **joint and per-grain BH**, and Layer A residualized syllable scalars do not separate condition arms under declared families ([[Joint vs Per-Grain FDR]]).

**We cannot honestly say:**

- That latent sequencing found recognition-linked SD effects that DR missed.
- That cluster integer ids are portable across models (ADR-0005).
- That more alphabet DA / Shannon fishing will salvage a clinical headline.

---

## Future directions

1. **Residual litmus** — [[F Residual-A]] / [[V Residual Litmus Null]] **fail** (0/6 FDR, 0/6 uncorrected). Syllable leftovers after speed / `frac_still` / `frac_near_nvl` are redundant for condition. Collinearity demo: raw M Shannon uncorrected p≈0.041 → residual p≈0.971.
2. **New sequence definitions only under contract** — no Family B on TransStruct / NGramSeq without user OK and a declared grain + BH family.
3. **Define investigation quality first** ([[H Investigation Quality]]) before more alphabet or per-animal accent fishing ([[H Alphabet Equating]]).
4. **Stop occupancy fishing as a career** — saturated for composition-as-condition-separator; the negative result *is* a product.

No invented next headline.

---

## Related

- [[Claim Kind]] · [[Artifact Linking]]
- [[T3 Syllable Task State]] · [[H Syllable Task State]]
- [[T4 Measurement Quality]] (Layer A V&V sits with measurement honesty)
- [[Run Syll Ambulation Overlap]] · [[Run Slides Pack]] · [[Run Object Prox DR]] · [[Run Transition Structure]]
- [[Run Per Animal Prototype Ordination]] · [[H Alphabet Equating]]
- [[V TransStruct Null]] · [[V NGramSeq Null]] · [[V TransStruct Cross-Campaign]] · [[V Residual Litmus Null]]
- [[NOR IMPRESS Index]] · [[Prune Map]]
- Hunt deck: `C:\Users\admin\Documents\work\davis lab\motion sequencing in NOR (impress).pptx`
