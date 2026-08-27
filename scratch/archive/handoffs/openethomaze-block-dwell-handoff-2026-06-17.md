# Handoff: Legacy block dwell averaging plots

**Repo:** `c:\Users\admin\code\OpenEthoMaze`  
**Date:** 2026-06-17  
**Status:** Feature implemented and run successfully on user test data; no commit requested.

---

## Goal

Script to average RUN-phase dwell heatmaps from `vast_results_legacy.h5` for the **ele cohort** (`researcher == Emma|Hayden`), stratified by **sex × strain × tx**, with trial blocks **1–3, 4–6, 7–9**, plus full-session **1–9**, plus **cross-session pooled** averages.

Design was resolved interactively (grill-with-docs). Glossary lives in repo root **`CONTEXT.md`** — do not duplicate; read that file for canonical terms.

---

## What was built

| Artifact | Path |
|----------|------|
| CLI entry | `uv run maze-average-block-dwell-plots` → `maze/cli/average_block_dwell_plots.py` |
| Core logic | `maze/pipeline/viz/block_dwell_average.py` |
| Tests | `tests/test_block_dwell_average.py` |
| Script registration | `pyproject.toml` → `maze-average-block-dwell-plots` |

### Run command (user data)

```powershell
uv run maze-average-block-dwell-plots `
  --db-path "c:\Users\admin\Documents\work\sack\test\vast_results_legacy.h5" `
  --manifest-path "c:\Users\admin\Documents\work\sack\test\trial_manifest_legacy.csv" `
  --out-dir "c:\Users\admin\Documents\work\sack\test\block_dwell_exports"
```

### Three output sets (one command)

| Set | Output root | ~PNG count (last run) |
|-----|-------------|----------------------|
| Per-session tri-blocks | `{out}/S##/{tx}/S##_tx_strain_sex_trial{1-3\|4-6\|7-9}.png` | 180 |
| Per-session T01–T09 | `{out}/trial1-9/` | 60 |
| Cross-session pooled | `{out}/all-sessions/` (+ `trial1-9/` subfolder for full session) | 48 |

Each set writes its own `summary.csv`. Pooled rows use `session=ALL` and filenames like `ALL_RBSF_wt_F_trial1-3.png`.

### CLI flags

- `--no-full-session` — skip `{out}/trial1-9/`
- `--no-all-sessions` — skip `{out}/all-sessions/`
- `--full-session-out-dir`, `--all-sessions-out-dir` — override pooled paths
- `--blocks`, `--sessions`, `--researcher`, `--phase`, `--max-dwell-s` — filters

---

## Locked design (see `CONTEXT.md` for full glossary)

- **Dwell average:** recompute from RUN-phase XY, average grids in seconds-space, render once (not PNG pixel average).
- **Dwell source:** H5 `ambulation_metrics/spot_hybrid/xy`, `trial_state == 'run'`.
- **Cohort:** `phase=experimental`, sessions `S01`–`S05`, `researcher='Emma|Hayden'` (literal string in CSV).
- **Block average:** mean trials within block per animal×session, then mean across units in stratum.
- **Partial blocks:** OK if ≥1 trial present.
- **Frame:** arena-normalized cm (`DISPLAY_ARENA_RADIUS_CM = 62`).
- **Colorbar:** fixed 4.0 s (`MAX_DWELL_TIME_S`).
- **Exits:** all contributing exit zones drawn, translucent green (`EXIT_OVERLAY_ALPHA = 0.85` in current code).
- **Filesystem:** manifest `tx=n/a` → path token `n_a` (slashes invalid on Windows).

---

## Bugs fixed during session

1. **`tx="n/a"` missing:** `pd.read_csv` treated `n/a` as NaN → fixed with `keep_default_na=False` in `_load_manifest_rows`.
2. **`n/a` paths:** `Path / "n/a"` split into `n\a\` → `tx_path_token()` replaces `/` with `_` in paths/filenames; `summary.csv` still reports `tx=n/a`.
3. **Cross-session pooling:** `average_block_dwell` groups by `(animal_id, session)` not `animal_id` alone, so S01 and S02 for the same animal are separate units.

---

## Summary CSV columns (current)

`session, tx, sex, strain, block, block_trials, n_animal_sessions, n_unique_animals, n_trials, output_path, colorbar_max_s`

---

## Not done / possible follow-ups

- **No git commit** was made (user rule).
- **Not identical to stored `composite_run`:** heatmap uses single `spot_hybrid` point, not all SLEAP nodes.
- **Arena display:** pooled plots use fixed 62 cm display radius; per-trial calibrations vary slightly (146–150 px radius, ~2.41–2.47 px/cm in cohort sample).
- **Sparse strata:** e.g. `tg` + `RBSF` had n=1 per sex in Emma|Hayden subset — plots still generated.
- **User may want:** exit overlay alpha tuning, global colorbar max across all plots, `scripts/README.md` entry, or promoting CLI in docs.
- **Workspace now includes** `c:\Users\admin\Documents\work\sack` — exports and H5 live there, not in repo.

---

## Key constants (`block_dwell_average.py`)

- `TRIAL_BLOCKS`, `FULL_SESSION_BLOCK` (`1-9`), `ALL_TRIAL_BLOCKS`
- `POOLED_SESSION_LABEL = "ALL"`
- `EXIT_OVERLAY_ALPHA = 0.85`

---

## Suggested skills

| Skill | When to use |
|-------|-------------|
| **grill-with-docs** | Further design changes (new strata, different averaging hierarchy, exit-aligned frame). |
| **verify-this** | Confirm export counts, n/a cohort coverage, or claim that pooled averages match intent. |
| **review** | Pre-commit review of uncommitted dwell-averaging changes. |
| **tdd** | Adding regression tests for manifest edge cases or H5 integration smoke. |
| **request-refactor-plan** | If splitting `average_block_dwell_plots.py` or extracting shared manifest loading. |
| **deslop** | Pass on new files before commit. |
| **to-issues** | Break follow-ups (docs, commit, integration test on full H5) into grabbable tasks. |

---

## Fresh agent quick start

1. Read `CONTEXT.md` at repo root.
2. Read `maze/pipeline/viz/block_dwell_average.py` and `maze/cli/average_block_dwell_plots.py`.
3. Run `uv run pytest tests/test_block_dwell_average.py -q`.
4. Re-run CLI against user paths above; inspect `block_dwell_exports/all-sessions/summary.csv`.
5. Ask user before committing.
