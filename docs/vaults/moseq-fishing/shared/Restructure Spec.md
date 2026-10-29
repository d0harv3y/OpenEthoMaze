---
title: Restructure Spec
type: ops
assay: nor-impress
status: na
claim_kind: na
verdict: na
tags:
  - claim/ops
  - assay/nor-impress
---
# Vault Restructure Spec: Theory–Hypothesis–Estimand

**Status:** restructure complete for NOR claim layer (**2026-10-06** CLI pass): YAML frontmatter on all notes; Bases (`Claims` / `Verdicts` / `Runs`); `E` notes in `estimands/`; score-contract stubs in `families/`; TransStruct proof-branch exit met; Concordance updated.
**Rule:** refile, never recompute. Verdicts move; numbers don't change.

## 1. Target tree

```
docs/vaults/openethomaze/          (the one vault)
  theories/
    T0 Altered Behavior.md         (bonus tier: plain condition effects, no winning link needed)
    T1 Recognition NOR.md          (SD alters recognition-linked behavior)
    T1 Flexibility VAST.md         (condition alters cognitive-flexibility behavior; hypotheses = fog)
    T1 Prodromal Alz.md            (stub until pose lands)
    T2 Physio Coupling.md          (gated on a T1 lock)
    T3 Syllable Task State.md
    T4 Measurement Quality.md      (Q4 + accent infrastructure)
  hypotheses/                      (renamed Q notes; see §6)
  estimands/                       (one note per scalar; see §3)
  families/                        (family specs: TransStruct-A pattern; see §3)
  assays/nor-impress/runs/         (unchanged names; estimates)
  assays/vast-alz/                 (unchanged)
  shared/                          (roots, ladder bridge, this spec, concordance)
  Prune Map.md                     (the lava list; stays at root, stays red)
```

## 2. Note types and mandatory headers

| Type | Prefix | Mandatory header |
|------|--------|------------------|
| Theory | `T` | claim in one line; child hypotheses; assay flavor |
| Hypothesis | `H` | plain question; parent theory; child estimands; status line |
| Estimand | `E` | scalar + FORMULAS row; grain; family + STATS rule; INTERPRET clause; strata parameters per assay; estimates table (campaign → run → verdict); status line |
| Family spec | `F` | cells; hit rule; member estimands |
| Estimate | `Run` (existing) | assay; campaign path; runner; design; verdict pointer; **Artifacts** table per [[Artifact Linking]] |
| Verdict | `V` | family; pass/fail; locked negative/positive language; status line |

Every claim note (`T`/`H`/`E`) carries a status line: `treasure` (supports parent, cite freely), `rabbit-hole` (open but demoted, with pointer to why), `lava` (do not reopen without new contract). Run verdicts read `ladder` (replicated/clean) or `snake` (looked like progress, confounded on recheck).

## 3. Estimand rules

- One note per scalar. Scalars that diverged (TV-distance confounded vs H clean null) never share a verdict.
- Shared across assays: strata parameterized per assay in the note (NOR `condition` vs VAST 4-condition are different contrasts — stated, never silent).
- Family specs (TransStruct-A pattern: cells + hit rule) live in `families/`; estimands point at them.
- Cross-assay links go through estimand notes and the ladder bridge only. No run-to-run cousin links.

## 4. Vocab spine

Vocab stays in `docs/vocab/`. Every `E` note cites by row/section: FORMULAS (scalar math), STATS (inference rule by use case), INTERPRET (what a hit means), CONTEXT (nouns), PROTOCOL-STRATA + BOSS-SESSION-MAP (wire). No duplication; broken row-links are treated as broken links.

## 5. Graph colors (by status, not folder)

| Color | Meaning |
|-------|---------|
| gold | treasure |
| violet | rabbit-hole |
| red | lava (Prune Map + lava notes) |
| green | ladder (clean runs/verdicts) |
| orange | snake (confounded hits) |
| blue-gray | T/H/E/F structure |

## 6. Rename table (all 23 question notes)

| Old filename | New filename | Parent |
|---|---|---|
| Q Accent Alphabet Equating | H Alphabet Equating | T4 (cross-listed T3) |
| Q0 Assay Validity NOR | H Assay Validity NOR | T1-NOR (prerequisite) |
| Q1 Condition Effect on DR | H Novelty Preference DR | T1-NOR |
| Q2 Behavior Physio Association | H Physio Coupling | T2 |
| Q2 Engagement Physio Honesty Pass | V Engagement Physio Null | T2 |
| Q2 Honesty Pass | V DR Physio Null | T2 |
| Q3 Syllable Task State | H Syllable Task State | T3 |
| Q4 Investigation Quality | H Investigation Quality | T4 |
| Q5 BoutGrammar Honesty Pass | V Visit Grammar Null | T1-NOR |
| Q5 BoutGrammar Score Contract | E Visit Grammar Counts | T1-NOR |
| Q5 Candidates Honesty Pass | V Candidate Lattice Null | T1-NOR |
| Q5 Condition Separating Behavior | H Recognition Separators | T1-NOR |
| Q5 Honesty Pass | V Engagement Delta Treasure | T0 (the treasure lives here) |
| Q5 Near Misses | V Near Misses Watchlist | T1-NOR (shared watchlist) |
| Q5 Occupancy Session-Delta Honesty Pass | V Occupancy Delta Null | T1-NOR |
| Q5 Occupancy Session-Delta Score Contract | E Occupancy Session Delta | T1-NOR |
| Q5 Recognition Honesty Pass | V Recognition Lattice Null | T1-NOR |
| Q5 SideMass Honesty Pass | V Side Geometry Null | T1-NOR |
| Q5 SideMass Score Contract | E Side Geometry | T1-NOR |
| Q5 Transition Structure Cross-Campaign Readout | V TransStruct Cross-Campaign | questions/ |
| Q5 Transition Structure Honesty Pass | V TransStruct Null | questions/ |
| Q5 Transition Structure Raw Exploratory | V TransStruct Raw Exploratory | questions/ |
| Q5 Transition Structure Score Contract | stub in families/ → E TransStruct TV Distance + E TransStruct Conditional Entropy + F TransStruct-A | done |

Rename is mechanical (script + link verify, zero broken links). Disputes about names come back to this spec.

## 7. Concordance format

`shared/Concordance.md`: two-column table old→new for all renames, kept forever for off-repo slide decks. Never deleted, only appended.

## 8. Proof-branch exit criteria

TransStruct **done** (2026-10-06): [[E TransStruct TV Distance]] + [[E TransStruct Conditional Entropy]] + [[F TransStruct-A]] with vocab headers and per-campaign estimates; V notes refiled (`V TransStruct *`); score-contract stub in `families/`; Obsidian unresolved = 0 (in-vault); Bases query Treasure/Lava/Fail.

## Related

- [Vault Restructure Map](../../../tickets/wayfinder-vault-restructure-map.md) (tracker; relative link, not a vault claim link)
