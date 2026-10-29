# Map: Vault Restructure to Theory–Hypothesis–Estimand

**Label:** `wayfinder:map` (local-markdown tracker: this file; child tickets are sibling files).

## Destination

A spec + skeleton + one migrated proof branch: the Obsidian vault reorganized from assay/runner-first into theory → hypothesis → estimand → estimate → verdict, with shared estimand notes across campaigns, vocab dispersed by row-link, and the TransStruct family fully migrated as proof. Someone opening the vault can travel from a theory to its verdicts without passing through runner folders.

## Notes

- Domain: Obsidian claim-graph (`docs/vaults/openethomaze/`); sessions consult `grilling`, `domain-modeling`, `obsidian-vault`.
- Standing preferences: `[[filename]]` links (moves are safe); `INFO_*.md` stays with data, never duplicated into vault; claim notes answer questions; commit only when asked.
- Statuses use the bestiary, formally: claim notes carry `treasure` / `rabbit-hole` / `lava`; run verdicts read as `ladder` / `snake`. Levity intended, meanings fixed in the spec.
- Theories are assay-aware: T1 splits per assay (NOR recognition, VAST/RAM cognitive flexibility, Alz prodromal); T0/T2/T3/T4 are shared.

## Decisions so far

- [Vault Restructure Spec](wayfinder-vault-restructure-spec.md): **resolved** — spec at `docs/vaults/openethomaze/shared/Restructure Spec.md` (tree, headers, estimand rules, spine, colors, 23-note rename table, concordance, exit criteria).
- [Shared Estimand Notes](wayfinder-vault-restructure-spec.md): one note per scalar, strata parameterized per assay, per-assay estimate sections.
- [Rename With Script and Concordance](wayfinder-vault-restructure-rename.md): **resolved** — 19 ops (7 merges + 12 renames), 53 files relinked, zero broken, concordance written; 4 TransStruct notes deferred to proof branch.
- [TransStruct Proof Branch Migration](wayfinder-vault-restructure-proof-transstruct.md): **resolved** — 2 E notes (#lava) + F TransStruct-A + 4 refiles (3 V-renames tagged, contract stubbed) + board pointer; zero broken. **Map complete: all tickets closed.**

## Follow-up (outside this map)

- [Gap Fill After Proof Branch](wayfinder-vault-gap-fill.md): **resolved** — FORMULAS TRANSITION rows added, bestiary tagged (11 lava / 1 treasure / 1 rabbit-hole / 1 snake / 1 ladder), graph re-verify left to user.
- [Per-Scalar Estimands](wayfinder-vault-restructure-proof-transstruct.md): TV-distance and H get separate notes (they diverged: confounded vs clean null).
- [Vocab Spine by Header](wayfinder-vault-restructure-spec.md): vocab stays in `docs/vocab/`; every estimand note carries a mandatory header citing its FORMULAS row, STATS rule, INTERPRET clause.
- [Theory Cut With Assay Flavors](wayfinder-vault-restructure-skeleton.md): T0 altered behavior (bonus tier) + T1 per assay + T2 coupling + T3 structure + T4 measurement.
- [Skeleton Built](wayfinder-vault-restructure-skeleton.md): **resolved** — theories/ (7), hypotheses/ (7 stubs), estimands/ + families/ (empty), status-based graph colors, README map, rename merge rule recorded.
- [Bestiary Statuses Formal](wayfinder-vault-restructure-spec.md): treasure / rabbit-hole / lava / ladder / snake as canonical status lines.

## Not yet specified

- VAST hypotheses under T1-flexibility (fog: runs exist, no hypotheses yet; graduates when a VAST claim is posed).
- Alz NOR theory instantiation (fog until pose extraction lands; placeholder lives in shared Campaign Roots).
- RAM coverage (named alongside VAST for cognitive flexibility; no inventory yet).
- Vocab row-link pass beyond the proof branch (all other estimands).
- Slides-pack / figure-note migration (media layer untouched by this effort).
- Full migration of remaining ~60 notes (only the proof branch migrates here).

## Out of scope

- New science or re-analysis (restructure only; verdicts are refiled, never recomputed) — see the closed question of recomputing honesty passes, ruled out in scoping.
- Physio follow-ups and Family B on failed scores (locked out by existing honesty passes).
- MAZE code or runner changes (vault-only effort).
- A second vocab vault (ruled out in Q9: spine-by-header instead).
