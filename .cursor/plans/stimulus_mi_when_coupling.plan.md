---
name: stimulus MI when-coupling
overview: Extend stimulus MI with per-trial estimates and ordinal exposure (trial_ord / cum_run_bouts), then animal-level slope and early−late delta summaries tested across sex / strain / tx — additive to the pooled animal pilot.
todos:
  - id: trial_ord
    content: Parse numeric session/trial suffixes → trial_ord; cum_run_bouts; fail-fast on unparseable
    status: pending
  - id: mi_per_trial
    content: "Per-trial MI full factorial; reuse cohort bin edges; optional --min-run-bouts/--min-h-stim (off by default)"
    status: pending
  - id: trial_nulls
    content: "--trial-nulls → circular only n_perm=200; default emit mi_mm without per-trial p"
    status: pending
  - id: animal_summaries
    content: "mi_trial_animal_summaries.csv: slopes/deltas on mi_mm (+ excess if nulls), trial mean/median, mean n_bouts/H_stim, clear fraction if nulls"
    status: pending
  - id: when_group_tests
    content: "group_mi_when_tests.csv primary cells only (run×duty|dist×occupancy); MW/Kruskal on slope + early_late_delta (+ excess metrics if nulls)"
    status: pending
  - id: cli_flags
    content: Extend maze-compute-stimulus-mi (--per-trial, --trial-nulls, optional gates); pooled path always still written
    status: pending
  - id: contracts_tests
    content: Contract md + synthetic tests (ord parse, k=3 delta, slope sign, primary vs full factorial emission)
    status: pending
isProject: false
---

# Stimulus MI — when is coupling real (trial + ordinal exposure)

## Goal

Answer “when along experience is stimulus↔syllable coupling present, and does that timing differ by sex / genotype / tx?” without reopening mixed models or replacing the pooled animal pilot.

Grill closed 2026-07-09. ADR: [docs/adr/0006-stimulus-mi-trial-trajectory-not-mixed.md](../../docs/adr/0006-stimulus-mi-trial-trajectory-not-mixed.md).

## Locked decisions (do not relitigate)

| Topic | Decision |
|-------|----------|
| Grain | **Trial** MI + **ordinal exposure** (`trial_ord` primary, `cum_run_bouts` secondary) |
| “Real” | Continuous **excess** (`mi_mm − null_circ_mean`) for analysis when nulls on; binary `null_circ_p < α` annotation only |
| `trial_ord` | Parse numeric suffixes from `session` / `trial`; fail-fast if unparseable |
| Early/late | **Career:** first/last **k=3** on `trial_ord` (all sessions); require **N ≥ 6**; delta = **mean(early) − mean(late)** on `mi_mm` (+ excess if nulls). **Within-session:** same k per session (\(N_{sess}≥6\)), animal scalar = mean of session deltas (`early_late_delta_within_session`); see sliced-factorial grill / plan |
| Strata×when | Animal-level **OLS slope** + **early_late_delta**; Mann–Whitney/Kruskal — **no** trial-level mixed model |
| Primary claims | `run × {duty, dist} × occupancy` only for when-tests |
| Trial CSV | **Full factorial** `phase × stim_var × mi_type` |
| Gates | Default **emit all trials**; optional `--min-run-bouts` / `--min-h-stim` |
| Bins | Reuse cohort-global `stimulus_bin_edges.json` (manual edits allowed; pass via existing load path) |
| Pooled | Keep `mi_per_animal.csv` / `group_mi_tests.csv`; `--per-trial` is **additive** |
| Nulls | Default: no per-trial p; `--trial-nulls` → circular, **n_perm=200** |
| Slopes | Default OLS of **`mi_mm` ~ trial_ord**; also excess slope when `--trial-nulls` |
| CLI | Extend `maze-compute-stimulus-mi` |
| Artifacts | `mi_per_trial.csv`, `mi_trial_animal_summaries.csv`, `group_mi_when_tests.csv` |

## Data flow

```mermaid
flowchart TD
  sbf["stimulus_bout_features.csv"] --> pt[compute --per-trial]
  edges["stimulus_bin_edges.json"] --> pt
  pt --> trial["mi_per_trial.csv (full factorial)"]
  trial --> summ["mi_trial_animal_summaries.csv"]
  summ --> when["group_mi_when_tests.csv (primary cells)"]
  sbf --> pooled[compute pooled animal MI]
  edges --> pooled
  pooled --> animal["mi_per_animal.csv"]
  animal --> groups["group_mi_tests.csv"]
```

## Out of scope

Mixed-effects time×strata; calendar-session as primary x (session still used to order); MI alphabet = n-grams/Behavior (ethogram track); probe/omission dissociation of duty vs proximity.
