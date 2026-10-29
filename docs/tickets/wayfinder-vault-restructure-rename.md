# Ticket: Rename With Script and Concordance

**Type:** `wayfinder:task` (AFK — scripted).
**Status:** closed (resolved this session).
**Resolution:** 19 ops executed by script (7 board merges into `hypotheses/`, 12 in-place renames in `questions/`), links rewritten across 53 files, zero broken verified, `shared/Concordance.md` written (all 23 rows). The 4 TransStruct notes were deliberately left at old names for the proof-branch ticket (contract splits three ways there).
**Blocked by:** [Vault Restructure Spec](wayfinder-vault-restructure-spec.md) (rename table lives in the spec).

## Question

Rename Q-notes to theory-scoped filenames via script, update all `[[links]]` vault-wide by filename match, verify every link resolves (same check as the assay-folder move: zero broken links), and write the concordance note mapping old→new names for off-repo slide decks. Rename is mechanical; any naming dispute goes back to the spec, not this ticket.

**Merge rule (skeleton pre-created 7 H-board stubs in `hypotheses/`):** for the 7 board-level renames (Assay Validity, Novelty Preference DR, Physio Coupling, Syllable Task State, Investigation Quality, Recognition Separators, Alphabet Equating), write stub header + existing Q body into `hypotheses/<H name>` and delete the old file — same zero-broken-links verify after.
