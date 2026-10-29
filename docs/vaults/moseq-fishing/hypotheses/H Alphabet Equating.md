---
title: H Alphabet Equating
type: hypothesis
assay: nor-impress
status: rabbit-hole
claim_kind: alphabet-bound
verdict: na
tags:
  - claim/hypothesis
  - assay/nor-impress
  - rabbit-hole
  - alphabet-bound
aliases:
  - Q Accent Alphabet Equating
---
# H Alphabet Equating

**Parent:** [[T4 Measurement Quality]] (cross-listed [[T3 Syllable Task State]]).
**Status:** infrastructure, open. #alphabet-bound

---

**Question:** Do pooled kpMS alphabets smear **animal-idiosyncratic pose embedding shift** (size / camera / gait “accent”), and does **fit-per-animal + kinematic remapping** recover cleaner cross-animal syllable physics?

**Layer:** infrastructure for Layer C / ADR-0005 — not preference, not physio, not a Q5 lock by itself.

**Status:** poked on `nor_per_animal_paramscan` (2026-09-28). Descriptive bearings only so far (D). Overview caveats still apply (`docs/vocab/NOR-IMPRESS-OVERVIEW.md` §8): data poverty, remapping DoF, quality score still undefined.

## What we mean by accent

Between-animal confounds in shared AR-HMM latents that can make integer syllable ids look portable when the kinematics are not. Prefer “animal-local alphabets, physics-based remapping” over “more unique syllables.”

## Pokes on this campaign

| Poke | Artifact grain | Result class |
|------|----------------|--------------|
| Syllable duration QC (sex × condition × `num_states`) | D heatmaps | Accent / alphabet inventory — [[Run Per Animal Syllable Descriptives]] |
| Bout kinematics table (144 × 9) | ADR-0005 feature table | Grain-agnostic — [[Run Per Animal Syllable Kinematics]] |
| Flat vs stage-1 prototype HDBSCAN + PCA | D ordination | Stage-1 = within-animal equate then across; params still exploratory — [[Run Per Animal Prototype Ordination]] |
| Soft NN + shape-of-bout + accent resid | D (pooled ∥ per-animal) | (0) leave-animal NN / nose–tail residualize; (1) peak/duty/Δelongation/… — [[Run Alphabet Equate Soft Shape]] |

Folder token `s2-3e4` = √10×10⁴ ≈ 31622.8 (not literal 30000).

## Not this question

- Condition separation ([[H Recognition Separators]]) — use declared scores; TransStruct on this campaign is a separate poke ([[V TransStruct Cross-Campaign]]).
- Investigation quality lock ([[H Investigation Quality]]) — still undefined; overview said Litmus before scaling; we ran descriptives/remapping bearings anyway.

## Related

- [[Run Per Animal Paramscan]]
- [[Run Per Animal Syllable Descriptives]] — figures on Run
- [[Run Per Animal Syllable Kinematics]]
- [[Run Per Animal Prototype Ordination]] — figures on Run
- [[Run Alphabet Equate Soft Shape]] — soft NN + shape (pooled ∥ per-animal)
- [[Run Prox Quad Per Animal]] · [[V Prox Quad Per Animal Exploratory]] — animal-local Prox/Quad composition DR lead
- [[Run Syllable Signatures]] (pooled cousin)
- [[Claim Kind]] · [[Artifact Linking]]
- [[H Syllable Task State]]
- [[H Investigation Quality]]
- [[Campaign Roots]]
- [[NOR IMPRESS Index]]
