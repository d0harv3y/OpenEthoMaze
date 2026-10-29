# Ticket: Unified ultra-legacy H5 (read-only merge)

**Status:** deferred sketch — do not start without an explicit go.  
**Origin:** PROTOCOL-STRATA campaign **Later** (on-disk H5 group/attr migration).  
**Related:** campaigns B/C (wire names live in code/CSVs; historical H5 trees untouched).

---

## Problem

Legacy cohorts live in several old H5 shapes (controller results, `vast_results_legacy`, EHRAM imports, NOR/kpMS sidecars, ele copies, …). Live `maze/` and `scratch/` analysis now assume the **current** protocol ladder and animal strata:

| Wire | Role |
|------|------|
| `session` → `trial` → `interval` (`run` \| `wait`) | within-animal ladder |
| `condition`, `sex`, `strain`, `drug`, … | animal strata (not ladder) |

Today: readers often special-case legacy attrs (`phase_layer`, `tx`, `iti_wait`, hab\|exp `phase`, RAM `SD`, …) at boundaries. That works for cutover but keeps **N databases × N adapters**.

## Idea (one big edit, then freeze)

When we *do* touch legacy H5s, prefer **one** migration that:

1. **Merges** all worth-keeping old DBs into a single **ultra-legacy** HDF5 (ugly is fine).
2. **Rewrites** group paths / attrs / band strings to the **current** wire contract (same as new controller H5 + manifests).
3. Marks the result **read-only forever** — no further schema churn; new acquisition stays on live DBs.
4. Lets **the same** `maze` / `scratch` loaders and analysis scripts run on ultra-legacy and on new data where the contract overlaps (pose, feedback, ambulation, manifests, kpMS apply keys, …).

Goal: never maintain a second analysis dialect — only a **frozen source** plus current code.

## Non-goals (for this ticket)

- Rewriting vendor PD Name/Value session dumps.
- Dual-write shims or permanent dual columns.
- Changing live acquisition / new trial H5 layout beyond what’s already shipped in B/C.
- Re-fitting kpMS or re-deriving scientific claims (migration is structural).

## Sketch — migration shape

```
sources (read)          one-shot migrator              sink (write once)
─────────────────       ─────────────────              ─────────────────
vast_results_legacy.h5  map groups/attrs/bands    →    ultra_legacy.h5
controller cohort *.h5  normalize session/trial        (gitignored / archive
EHRAM imports           remap RAM SD→TX, …              volume; checksummed)
NOR/ele leftovers       drop hab|exp phase column
                        copy datasets byte-stable
                        provenance: source path +
                          content hash per trial
```

**Compatibility bar:** after migration, `list_trials` / `TrialKey` / `load_manifest_csv` / feedback+xy join / kpMS recording keys resolve without legacy-only branches *for this file*. Temporary read shims may remain for unre-migrated files until cutover completes.

## Design north star — Neurodata Without Borders (NWB)

When this migration *does* run, endeavour to align the frozen ultra-legacy (and any new export path) with **[NWB](https://nwb-schema.readthedocs.io/en/latest/index.html)** (Neurodata Without Borders) rather than inventing a third OEM-only dialect.

Practical reading for this ticket:

- Prefer mapping concepts onto NWB types where they already exist (`Subject`, `TimeIntervals` / epochs, behavior `SpatialSeries` / `Position`, `ProcessingModule`, external video via `ImageSeries`, …) instead of freeform `/animal/session/trial/` trees alone.
- OEM wire names (`session` → `trial` → `interval`, animal strata) should remain the **analysis vocabulary**; NWB is the **on-disk interchange** target for the frozen DB where feasible.
- Full byte-identical NWB compliance may be phased (ndx extension for maze-specific feedback / kpMS ethogram if core types are insufficient). Document gaps rather than fake compliance.
- Spec entry point: https://nwb-schema.readthedocs.io/en/latest/index.html
- **Potential OEM add-in:** [NeuroConv](https://neuroconv.readthedocs.io/) (`neuroconv` / [catalystneuro/neuroconv](https://github.com/catalystneuro/neuroconv)) — convert / combine streams into NWB with format `DataInterface`s (behavior gallery already includes SLEAP, DeepLabCut, video). Prefer a thin OEM→NeuroConv interface over a one-off `pynwb` writer if/when we export. Not installed today; declare as an optional `uv` extra only after a spike proves fit.

## Open design questions (answer before coding)

1. **Scope of “all”:** which on-disk H5 roots are in (lab drives, sack, ele, IMPRESS)? Inventory first.
2. **Identity merge:** how to collide animal/session/trial across sources (prefix? cohort attr? reject overlaps?).
3. **Pose / video paths:** rewrite to portable roots vs leave absolute and document machine map.
4. **Partial trials / mistrials:** keep as-is with current mistrial attrs; no re-analyze in migrator.
5. **Verification:** litmus set — open N trials, compare key datasets (xy length, feedback align, syllable keys) pre/post; checksums.
6. **Delivery:** single file vs sharded by assay (`ultra_legacy_vast.h5`, …) still “one dialect.”
7. **NWB depth:** native `.nwb` via `pynwb` / **NeuroConv** vs NWB-shaped groups inside a multi-animal H5 vs export-on-demand adapter from current OEM layout.

## Suggested milestones (when un-deferred)

1. Inventory + size/overlap report (no writes).
2. Written contract: ultra-legacy ≡ current H5 layout (link `h5_tracking_contract` / cohort layout docs).
3. Dry-run migrator → temp file; V&V litmus.
4. Freeze write; point discovery/defaults at ultra-legacy for historical cohorts only.
5. Delete or archive source DBs after checksum attestation (optional, separate approval).

## Acceptance (sketch)

- [ ] One (or few assay-sharded) ultra-legacy H5(s) with **current** group/attr names only — **or** NWB / NWB-export layout per the north-star note above.
- [ ] Documented provenance map `source_h5 + old_path → new_path`.
- [ ] Same analysis entrypoints run on ultra-legacy and a modern cohort without legacy column forks.
- [ ] Explicit “do not mutate” note in AGENTS / paths docs.
- [ ] Written gap list vs [NWB schema](https://nwb-schema.readthedocs.io/en/latest/index.html) (what maps cleanly vs needs `ndx-*` / LabMetaData).

---

*Filed as an in-repo ticket because GitHub CLI (`gh`) was not available on the authoring machine. Promote with:*

```powershell
# after: winget install GitHub.cli   (user runs install)
cd C:\Users\admin\code\OpenEthoMaze
gh issue create --title "Unified ultra-legacy H5 (read-only merge)" --body-file docs/tickets/unified-ultra-legacy-h5.md
```
