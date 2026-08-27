# Handoff: Behavioral ethogram — TDD implementation

**Date:** 2026-06-16  
**Repo:** `C:\Users\admin\code\OpenEthoMaze`  
**Prior transcript:** `C:\Users\admin\.cursor\projects\c-Users-admin-code-OpenEthoMaze\agent-transcripts\eaf93259-b3b4-4b5f-b354-6fdf20defb51\eaf93259-b3b4-4b5f-b354-6fdf20defb51.jsonl`

**Next session focus:** Test-driven implementation of **Phase I** (and first **Phase II** hooks) per locked design. User deferred platform context-tag / manifest `apparatus` work (see `my_todo.txt` line 14).

---

## Goal

Turn grill-locked behavioral ethogram design into tested scratch code:

1. Extend Phase I clustering with scalar sidecars, bout-speed IQR, `ambiguous` flag.
2. Align output paths with storage ADR (`behavior_ethogram/` not mixed with PNG exports).
3. Add unit tests (no GPU, synthetic kinematics) before long test2 runs.
4. Then: cross-stream contrast join, tier calibration script, block-ethogram tier coloring.

---

## Authoritative design (do not re-grill)

| Artifact | Path |
|----------|------|
| Glossary | `scratch/kpms_ensemble_compare/CONTEXT.md` |
| ADRs 0001–0010 | `scratch/kpms_ensemble_compare/docs/adr/` |
| Build order + storage | `scratch/kpms_ensemble_compare/BEHAVIORAL_ETHOGRAM_PLAN.md` |
| Label roadmap (not v1 scope) | `scratch/kpms_ensemble_compare/ONTOLOGY.md` |
| Product ethogram contract | `docs/ethogram_scope.md` |

**Phases:** I (tokens) → II (locomotion tiers) → IIIa (still freeze/groom) → IIIb (full names).

**Locked knobs:** anatomical primary; `phase=all` for clustering; blob/fused contrast stored in Phase I, used in Phase III; `is_moving` provisional; ambiguous = prototype bout speed IQR.

---

## Code already shipped (scratch, may be uncommitted)

| Module | Status |
|--------|--------|
| `scratch/kpms_ensemble_compare/syllable_speed_cluster.py` | `--scope per-stream`, per-model + stream clustering, seed in labels, stream motif grid, `cluster_run*.json` |
| `scratch/kpms_ensemble_compare/block_ethogram_exports.py` | Block ethograms v2, `--speed-reindex`, DATA_DICTIONARY companion section |
| `scratch/kpms_ensemble_compare/movement_layer.py` | Speed m/s fix (`px_per_cm`); `INCOMPLETE_MODELS` removed |
| `run_compare.py`, `export_wide_metrics.py`, `visualize_three_stream_overlay.py` | `INCOMPLETE_MODELS` removed; `--exclude-model` on compare |
| `pyproject.toml` | `hdbscan` in `kpms` extra |

**Smoke:** per-stream single-seed (`anatomical/seed_042`, `--phase run`) OK under `test2/.../speed_cluster_test/`.

**Not implemented yet (TDD targets):**

- Scalars on labels: `frac_still`, `mean_abs_dheading`, `bout_speed_iqr`, `ambiguous`
- Default `--out-dir` → `{kpms_root}/behavior_ethogram/phase_i` (ADR 0009)
- `contrast_sidecar.csv` (anatomical ↔ blob ↔ fused join)
- `calibrate_locomotion_tiers.py` + `locomotion_tiers.yaml`
- `block_ethogram_exports.py --tier-color` (token → tier lookup)
- **No tests** under `tests/` for ensemble scratch yet

---

## Data paths (test2 cohort)

| Resource | Path |
|----------|------|
| kpMS root | `C:\Users\admin\Documents\work\sack\test2` |
| Legacy ambulation | `C:\Users\admin\Documents\work\sack\test\vast_results_legacy.h5` |
| Manifest | `C:\Users\admin\Documents\work\sack\test2\trial_manifest_kpms_tracking.csv` |
| Tracking H5 | `test2/kpms_tracking.h5` |
| Viz exports (today) | `test2/block_ethogram_exports/` |
| **Target** cohort tables | `test2/behavior_ethogram/phase_i/` (create on implement) |

15/15 models have `results_apply.h5` on test2. Legacy H5 always from **test**, not test2.

User command templates: `my_todo.txt` lines 44–81 (note: clustering `--out-dir` should migrate to `behavior_ethogram/` when implemented).

---

## Out of scope (this session)

- Manifest `apparatus` column / generalized context-tag join (user todo; ADR 0010 is design-only)
- Phase IIIa exemplar picker / human review UI
- Promote scratch → `maze/cli`
- NOR controller
- Full 15-model ethogram PNG sweep
- `is_moving` debounce retune

---

## Suggested TDD order

### 1. Pure functions first (`tests/test_behavior_ethogram_phase_i.py` or similar)

Extract/test without H5/GPU:

- `extend_features_tmax`, `align_stats_tmax`
- `build_speed_rank_table` / keyed variants
- Bout speed IQR → `ambiguous` threshold helper
- Scalar aggregation from synthetic `MovementSeries` chunks
- `parse_stream_jobs` / `resolve_available_seeds`

Use `pytest`; `uv sync --extra dev --extra kpms` for `hdbscan` integration tests (mark optional).

### 2. Wire into `syllable_speed_cluster.py`

- Add columns to `hdbscan_labels.csv` / sidecar
- Set `ambiguous` before Phase II
- `--phase all` as default for behavioral pipeline (ADR 0006); keep CLI override

### 3. Storage path migration

- `--out-dir` default `{kpms_root}/behavior_ethogram/phase_i`
- `block_ethogram_exports.py --behavior-root` for lookups
- Update `my_todo.txt` templates after change

### 4. Integration smoke (manual / slow)

```powershell
uv run python scratch/kpms_ensemble_compare/syllable_speed_cluster.py `
  --scope per-stream --phase all --models anatomical `
  --kpms-root "C:\Users\admin\Documents\work\sack\test2" `
  --legacy-db "C:\Users\admin\Documents\work\sack\test\vast_results_legacy.h5" `
  --manifest-path "C:\Users\admin\Documents\work\sack\test2\trial_manifest_kpms_tracking.csv" `
  --out-dir "C:\Users\admin\Documents\work\sack\test2\behavior_ethogram\phase_i"
```

(~40+ min for 5 seeds — run after unit tests green.)

### 5. Phase II slice

- `calibrate_locomotion_tiers.py` with histogram PNGs + default YAML
- Tests on synthetic token scalar table → tier assignment

---

## Commands

```powershell
cd C:\Users\admin\code\OpenEthoMaze
uv sync --extra dev --extra kpms
uv run pytest tests/test_behavior_ethogram_phase_i.py -q   # after creating
uv run ruff check scratch/kpms_ensemble_compare/
uv run pytest tests/ -q   # regression before/after extractions
```

---

## Suggested skills

| Skill | When |
|-------|------|
| `debug-python` | pytest-first, `uv sync` deps, focused test runs |
| `investigation` | Only if H5 join paths or frame alignment unclear |
| `review` | After first TDD slice lands, review branch vs ADRs |
| `grill-with-docs` | **Do not** re-run unless user reopens design |
| `handoff` | End of next session if context fills again |

---

## Gotchas

- Raw syllable IDs **not comparable across seeds** — use per-stream `shared/` tokens.
- `speed_rank_table` from pre–speed-fix clustering is stale; re-cluster after `movement_layer` speed fix.
- `is_moving` = debounced speed threshold; secondary to `mean_speed_mps` (ADR 0002).
- Scratch imports via `sys.path` insert; tests may need `pythonpath` from `pyproject.toml`.
- Do **not** write token tables into `kpms_tracking.h5` or `vast_results_legacy.h5` (ADR 0009).
- No git commits unless user asks.

---

## Success criteria for TDD session

- [ ] New test file with ≥5 focused tests on Phase I pure logic (green)
- [ ] `hdbscan_labels.csv` includes scalar + `ambiguous` columns
- [ ] Outputs land under `behavior_ethogram/phase_i/` by default
- [ ] `uv run pytest` relevant subset passes; no scientific behavior change without test coverage for new fields
