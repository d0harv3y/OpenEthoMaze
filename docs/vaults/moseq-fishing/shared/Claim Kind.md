---
title: Claim Kind
type: ops
assay: nor-impress
status: na
claim_kind: mixed
verdict: na
tags:
  - claim/ops
  - assay/nor-impress
  - mixed
---
# Claim Kind

Binary tag on **claims** (H / V / Honest Report rows) — not on folders, not a Family.

| Tag               | Meaning                                                                                                                                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `#clock-portable` | Points at movement / proximity / stillness / occupancy clocks a **threshold + debounce** (or object-prox gate) segmenter can already name — no syllable alphabet required |
| `#alphabet-bound` | Needs the **kpMS** (keypoint-MoSeq) syllable stream: ids, composition over alphabet, transitions, n-grams, kinematic remapping                                            |

## Rules

- Tag the **claim**, not the Run. A Run can produce both kinds (e.g. [[Run Slides Pack]]: `frac_still/` is clock-portable; `shannon/` is alphabet-bound).
- `#clock-portable` includes Layer A V&V concordance (kpMS *reproducing* the classic clock) — still not MoSeq insight.
- `#alphabet-bound` includes sequence nulls **and** composition rediscovery — both need an alphabet; only sequence asks what thresholding *cannot*.
- **Do not** mint a Family (`F`) for figure packs or V&V decks. Family = declared BH inferential family only ([[Restructure Spec]]).
- Figures for either kind live on the **Run** ([[Artifact Linking]] § Figures); embed on V / report only when selling that claim.

## Quick map (NOR IMPRESS)

| Kind | Examples |
|------|----------|
| `#clock-portable` | [[V Engagement Delta]], [[V Protocol Step Clocks]], [[F Stillness-Companion-A]], [[H Assay Validity NOR]], [[H Novelty Preference DR]], [[V Occupancy Delta Null]], [[V Visit Grammar Null]], [[V Side Geometry Null]], Layer A concordance on [[Motion Sequencing Honest Report]] |
| `#alphabet-bound` | [[V Composition Step Fishing]], [[V TransStruct Null]] (+ B/C/PerGrain), [[V NGramSeq Null]] (+ B/C/PerGrain), [[V Residual Litmus Null]], [[V Composition Companion Partial]], [[H Alphabet Equating]], [[H Syllable Task State]] composition decks |

## Related

- [[Artifact Linking]] · [[Motion Sequencing Honest Report]] · [[T4 Measurement Quality]]
