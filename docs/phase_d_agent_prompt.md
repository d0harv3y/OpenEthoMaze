# Phase D agent prompt (copy into a new Cursor chat)

Use when continuing **Phase D — Structural paydown** on OpenEthoMaze.

---

## Prompt — next PR (start at D1 unless a slice is already open)

**Use for the next unchecked D task.** One PR per slice; run tests before and after each extraction.

```
Implement Phase D from docs/rescue_plan.md. Scope Phase D only — no Phase E ethogram features.

## Objective

Maintainability without a big-bang rewrite: agent docs, script hygiene, IMPRESS path quarantine,
then incremental main_window.py extractions (~2619 lines today → target ~500–800).

## Prerequisites (must hold)

- Phase A complete; Phase C product pipeline shipped (menus + kpMS + QC + overlay).
- uv sync --extra dev; uv run pytest tests/ -q is green before you start and after each PR.
- Do not change scientific behavior while splitting GUI — move code, wire imports, keep signatures.

## Done in repo (do not redo)

- Phase A–C per docs/rescue_plan.md (tests/, paths, CI, local-service, pipeline GUI, C8/C9).
- scripts/README.md lists maze.cli entry points; shims under scripts/*.py delegate to maze.cli.
- pytest pythonpath = ["tests", "."] — controller fixtures use pytest_plugins =
  ["controller.local_service.fixtures"] (not tests.* — site-packages may shadow tests/).

## Phase D order (one PR each)

### D1 — Agent + script docs (do first if not done)

| Deliverable | Path / notes |
|-------------|----------------|
| AGENTS.md | Repo root: install (uv sync extras), paths_local, pipeline GUI map, prefilter_mode, pytest/ruff/black, what not to edit (scripts/archive/) |
| scripts/README.md | Extend with **maintained / promoted / archive** table per rescue_plan § Scripts classification |
| Cursor rules | `.cursor/rules/openethomaze-*.mdc` — paths, gui-split, scripts, prefilter (short, actionable) |

### D2 — IMPRESS path quarantine

- Remove or gate lab-specific defaults in maze/kpms/* and maze/cli/legacy_db.py (no E:\ / IMPRESS in library defaults).
- Prefer paths.py / paths_local.example.py / env / CLI args.
- Add or extend tests/test_paths_portable.py if new constants move.

### D3 — Script hygiene

- Docstrings on promoted CLIs; archive langfuse demo → scripts/demos/ or scripts/archive/ (ruff-excluded archive is frozen — do not add features there).
- D5 (can follow D3): promote thin scripts to [project.scripts] only when maze.cli entry already exists and shim is redundant.

### D4 — main_window.py split (highest risk — strict order)

Extract modules under maze/controller/acquisition/gui/; each helper takes window: MainWindow.
MainWindow stays the composition root (menus, config, trial_controller wiring).

| Slice | New module (approx.) | Risk |
|-------|----------------------|------|
| D4a | legacy_exit_seed.py (~70 lines, H5 path heuristics) | Low |
| D4b | preview_events.py (eventFilter) | Low |
| D4c | profile_menu_actions.py, pipeline_menu_actions.py | Medium |
| D4d | status_and_config_sync.py | Medium |
| D4e | window_layout.py (__init__ UI build) | Medium |
| D4f | camera_loop.py (~750 lines) | **High — last big chunk** |
| D4g | trial_run_actions.py | Medium |

After each slice: uv run pytest tests/ -q; smoke GUI only if you touched camera_loop or trial run.

### Out of scope for Phase D

- Phase E ethogram materialize/fit (docs/ethogram_scope.md).
- Re-enabling SLEAP trace-quality tab or DeepLabCut backend.
- LLM/YOLO inside Qt (subprocess / maze-local-service only).
- Editing scripts/archive/** for new behavior.
- Phase B v1.1 h5web-unified long-lived service (optional; not blocking D).

## Conventions

- Match existing style; minimal diff per PR; no speculative abstractions.
- GUI imports at top of file (no inline imports in hot paths unless existing pattern).
- Commit only when the user asks.

## Verify

uv sync --extra dev; uv run ruff check maze tests; uv run pytest tests/ -q
```

---

## Prompt — Phase D complete (after D1–D5 + main_window target met)

**Use only when AGENTS.md exists, main_window is ≤~800 lines, tests green, and no open D regressions.**

```
Phase D (Structural paydown) for OpenEthoMaze is complete. Fix regressions only.

## Shipped structure

| Area | Outcome |
|------|---------|
| Docs | AGENTS.md, scripts/README classification, openethomaze cursor rules |
| Paths | No IMPRESS/E:\ defaults in maze/ library code |
| GUI | main_window.py ~500–800 lines; logic in gui/*_*.py helpers |
| CLI | Promoted entry points documented; demos archived |

## main_window companions (expected)

legacy_exit_seed, preview_events, profile_menu_actions, pipeline_menu_actions,
status_and_config_sync, window_layout, camera_loop, trial_run_actions

(Pipeline menus may still delegate to pipeline_dialogs, kpms_*_dialog, qc_summary_dialog, overlay_dialog.)

## Verify

uv sync --extra dev; uv run pytest tests/ -q

## Next

- Phase E: ethogram — docs/ethogram_scope.md (E0 library path can start without GUI).
- Optional: Phase B v1.1 unified h5web via long-lived service — rescue_plan § v1.1 follow-ups.
```

---

## Prompt — D5 script hygiene (shipped)

**Completed:** `maze-kpms-fit` / `maze-kpms-apply` in `[project.scripts]`; shims `scripts/kpms_fit.py`, `scripts/kpms_apply.py`; extended `scripts/README.md`; `tests/test_project_scripts.py`; Langfuse demo under `scripts/demos/` only.

---

## Prompt — next PR (D5 script hygiene + optional D follow-ups)

**Use after D4g is merged; main_window companions complete (~805 lines).**

```
Implement Phase D slice D5 only: script / CLI hygiene per docs/rescue_plan.md § Scripts classification.

Rules:
- One PR focused on D5: promote or document thin scripts where maze.cli entry already exists;
  archive langfuse demo if still at scripts/ root; extend scripts/README.md maintained/promoted/archive table.
- Do not edit scripts/archive/** for new behavior (frozen).
- Do not reopen main_window splits unless fixing a regression from D4f/D4g.
- uv run pytest tests/ -q must pass before PR is done.

Out of scope for this PR (separate tickets — see my_todo.txt):
- Settings dialog Apply/dirty-state UX (modeless dialog; users forget Apply).
- treatment_labels.csv eager load on maze-daq startup (defer; controller H5 should not need repo inputs/ reload).

Report: scripts reclassified, new/retired entry points, test result.
```

---

## Prompt — follow-up (treatment labels — not D5)

**Use when maze-daq must stop loading repo inputs/treatment_labels.csv on every launch.**

```
Fix treatment_labels loading for controller acquisition (Phase D follow-up, not ethogram).

Problem: maze-daq prints "Loaded N treatment labels from …/inputs/treatment_labels.csv" at startup.
Controller sessions use <output_dir>/trials.h5; cohort labels should come from <output_dir>/treatment_labels.csv
only when Discovery sync or kpMS enrich runs — not on every GUI launch.

Rules:
- Trace call sites (load_treatment_labels, enrich_manifests_from_treatment_labels, manifest_subset.load_manifests,
  process_trial._animal_notes_from_treatment_csv); defer or gate loads.
- Prefer default_treatment_labels_path(config) over repo inputs/ when output_dir is set.
- Keep mtime cache; demote stdout print to logging.debug (or print once per process at INFO).
- No behavior change for legacy_db / explicit Discovery sync paths.
- uv run pytest tests/ -q; extend tests/test_treatment_labels_csv.py or test_controller_discovery.py if paths change.

Report: call graph before/after, when labels load now, test result.
```

---

## Prompt — D4g trial_run_actions (shipped)

**Completed:** `maze/controller/acquisition/gui/trial_run_actions.py`; main_window ~805 lines.

```
Implement Phase D slice D4g only: trial_run_actions.py from main_window.py (~400–500 lines).

Rules:
- Move trial run / session control only: run timer tick, start/stop run, trial state change,
  trial recorder stop/flush, start/previous/next trial, session controls, virtual trial clock helpers.
- Keep in main_window.py: composition root, menus, settings/analysis dialogs, camera hooks (delegate to camera_loop),
  closeEvent, MC connect, file/H5 actions.
- Helpers take window: MainWindow; no behavior changes; no unrelated refactors.
- Do not move camera_loop or pipeline menu code in this PR.
- uv run pytest tests/ -q must pass before PR is done.
- Read docs/rescue_plan.md § main_window split — D4f (camera_loop) must already be shipped.

Smoke (manual): output_dir must exist (no missing drive); virtual video → scrub → Start trial → Stop;
confirm recording only when output path is writable.

Report: lines removed from main_window.py, new module path, test result.
```

---

## Prompt — D4f camera_loop (shipped)

**Completed:** `maze/controller/acquisition/gui/camera_loop.py`; main_window ~1095 lines (was ~1950).

```
Implement Phase D slice D4f only: camera_loop.py from main_window.py (~750 lines).

Rules:
- Move camera/preview loop code only; MainWindow keeps public hooks used by menus and trial_controller.
- Helpers take window: MainWindow; no behavior changes; no unrelated refactors.
- uv run pytest tests/ -q must pass before PR is done.
- Read docs/rescue_plan.md § main_window split — do not skip slice order.

Report: lines removed from main_window.py, new module path, test result.
```

---

## Prompt — single slice only (D4 example)

**Use when the user wants exactly one extraction PR.**

```
Phase D slice only: D4f camera_loop.py from main_window.py.

Rules:
- Move camera/preview loop code only; MainWindow keeps public hooks used by menus and trial_controller.
- No behavior changes; no unrelated refactors.
- uv run pytest tests/ -q must pass before PR is done.
- Read docs/rescue_plan.md § main_window split for slice order — do not skip ahead of open dependencies.

Report: lines removed from main_window.py, new module path, and test result.
```

---

## Notes

- Master plan: [rescue_plan.md](rescue_plan.md) § Phase D.
- Phase C handoff: [phase_c_agent_prompt.md](phase_c_agent_prompt.md) (complete prompt).
- Subagent resume ID (if splitting work): `0bf9a04e-5796-4397-920c-6ff10661673a`.
- Ethogram is parallel, not blocking: [ethogram_scope.md](ethogram_scope.md).
