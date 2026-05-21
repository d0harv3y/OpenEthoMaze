# OpenEthoMaze rescue plan (master)

**Verdict:** Rescue incrementally — do not rebuild. This document merges Phase A–D plans produced by delegated exploration subagents (May 2026).

**Related:** [roadmap.md](roadmap.md), unified HTTP plan at `.cursor/plans/unified_local_http_service_57353264.plan.md`.

---

## Overview

| Phase | Goal | Duration (rough) | Blocks |
|-------|------|------------------|--------|
| **A** | Stop the bleeding: tests, CI, deps, paths | 1–2 weeks | — |
| **B** | Unified localhost HTTP (`/orm/*` + h5web) | **Done** | A (tests + `local-service` extra) |
| **C** | Product narrative: re-enable pipeline GUI, kpMS fit | 2–4 weeks | A; B optional |
| **D** | Structural paydown: GUI split, AGENTS, scripts | Ongoing after A | A tests green per PR |
| **E** | Ethogram: materialize, apply batch, fit ops, exports | After A; overlaps C | See [ethogram_scope.md](ethogram_scope.md) |

```mermaid
flowchart LR
  A[Phase A Safety net]
  B[Phase B Local HTTP]
  C[Phase C Product]
  D[Phase D Structure]
  A --> B
  A --> C
  A --> D
  B -.-> C
  D -.-> C
```

---

## Delegation map (subagents)

Use `resume` with agent IDs to continue implementation in focused threads.

| Phase | Agent ID | Scope |
|-------|----------|--------|
| A | `6e35dbe4-743d-4847-94ac-c43a723ed4b6` | Tests, CI, pyproject extras, paths hygiene |
| B | `db6358f5-df99-4fc7-ad41-3a5fb627f4c6` | `local_service`, h5web refactor, `/orm/*` |
| C | `dd7ff43b-174c-4ce8-895a-af19af6dc384` | Discovery/inference menus, kpMS GUI, observability |
| D | `0bf9a04e-5796-4397-920c-6ff10661673a` | `main_window` split, AGENTS.md, scripts, cursor rules |

---

## Phase A — Stop the bleeding

**Objective:** Behavioral safety net and portable installs so later phases do not add decay.

### Tasks (ordered)

| ID | Task | Owner | Files |
|----|------|-------|-------|
| A1 | Un-ignore `tests/`; add `conftest.py` + first unit tests | Agent | `.gitignore`, `tests/**` |
| A2 | Neutral `paths.py` + `paths_local.example.py` | Agent | `maze/pipeline/paths.py`, `paths_local.example.py` |
| A3 | Remove lab defaults from `apply.py`, `legacy_db.py` | Agent | `maze/kpms/apply.py`, `scripts/legacy_db.py` |
| A4 | Split deps: lean core + `gui`, `sleap`, `local-service` extras | Agent + human `uv lock` | `pyproject.toml`, `uv.lock` |
| A5 | Fix README install lines | Agent | `readme.md` |
| A6 | 5–10 unit tests (see below) | Agent | `tests/test_*.py` |
| A7 | GitHub Actions: ruff, black, pytest | Agent | `.github/workflows/ci.yml` |
| A8 | Secondary path cleanup (JSON, profiles, script docstrings) | Human/Agent | `inputs/`, `maze/controller/profiles/` |
| A9 | Per-machine: copy `paths_local.example.py` → `paths_local.py` | Human | gitignored |

### First tests (pytest, no H5/video in git)

1. `parse_video_filename` / `parse_sleap_filename` — `file_discovery`
2. `trial_manifest_csv_row_values` — manifest CSV contract
3. `expand_filter_arg`, `filter_manifests_by_trial_selectors` — kpms apply
4. `canonical_ram_trial`, `TrialKey.path` — trial keys
5. `detect_trial_data_quality` — `trial_quality`
6. `trial_matches_frame_policy` — `trial_filters`
7. `filter_manifests` — kpms subset

### Acceptance (phase gate)

- `uv run pytest tests/ -q` passes on Ubuntu CI without GPU/GGUF
- `uv sync` (no extras) succeeds on CI
- No `E:\` / `IMPRESS` defaults in `maze/` library code
- `tests/` tracked in git

### PR sequence

1. **PR-A1:** A1 + A2 + A3 + `paths_local.example.py`
2. **PR-A2:** A4 + A5 + human regenerates lockfile
3. **PR-A3:** A6 + A7

### Tools / skills

- `debug-python` rules: `uv run ruff`, `pytest`, `black --check`
- **fix-ci** / **loop-on-ci** after workflows exist
- **review-and-ship** before merge

---

## Phase B — Unified local HTTP service

**Status:** **Complete (B0–B8, May 2026).** v1 HTTP stack is feature-complete; v1.1 polish tracked below.

**Objective:** One long-lived Flask process: h5web + h5grove + `/orm/*` (discover, detect, health). See `.cursor/plans/unified_local_http_service_57353264.plan.md`.

**Shipped layout:**

- **Core:** `h5grove[flask]` (h5web routes + CI tests without GUI).
- **`local-service` extra:** `waitress`, `llama-cpp-python`, `ultralytics`; script `maze-local-service`.
- **Package:** `maze/controller/local_service/` (sandbox, discover, detect, health).
- **GUI:** `maze/controller/local_service_launcher.py` + **File → Start local ORM service…** (subprocess; no LLM/YOLO in Qt).
- **Ephemeral h5web** (GUI **Open H5 in h5web**) still uses in-thread Flask on port 0 until v1.1 (see decisions).

### Tasks (ordered) — all done

| ID | Task | Files |
|----|------|-------|
| B0 | `local-service` extra + `maze-local-service` script | `pyproject.toml` |
| B1 | `register_h5web_routes(app, ...)`; thin `create_app` | `h5web_server.py` |
| B2 | Path sandbox | `local_service/sandbox.py`, `glob_safe.py`, `config.py` |
| B3 | `create_local_app`, waitress `__main__` | `local_service/app.py`, `__main__.py` |
| B4 | `GET /orm/health` | `routes/health.py` |
| B5 | `POST /orm/discover` | `llm.py`, `discover.py`, `routes/discover.py` |
| B6 | `POST /orm/detect` | `yolo.py`, `routes/detect.py` |
| B7 | Tests (sandbox + Flask client; no GGUF in CI) | `tests/controller/local_service/` |
| B8 | GUI subprocess launcher | `menus.py`, `local_service_launcher.py` |

### API summary

- `GET /orm/health` — version, roots, llm/yolo loaded flags
- `POST /orm/discover` — `{"query","limit"}` → globs + matches under data root
- `POST /orm/detect` — multipart image or JSON video path + frame index
- h5web: `/`, `/api/*`, `?file=<relative-to-data-root>`

### Security (v1)

- Bind `127.0.0.1` by default
- All paths via `resolve()` + prefix check under `--data-root`
- LLM output: JSON only; capped globs/time/matches
- No auth v1 (localhost threat model)

### Phase gate — passed

- Sandbox tests green in CI (`uv sync --extra dev`)
- `uv sync --extra local-service` documented; CI does **not** require GGUF
- GUI ephemeral h5web still works (B1 backward compat)
- Launcher does not require GGUF

### Locked decisions (Phase B + product direction, May 2026)

| # | Topic | Decision |
|---|--------|----------|
| 1 | **Discover / LLM** | **No GGUF configured** → keyword/glob fallback (`mode: "keyword"`); CI uses this. **GGUF configured** → LLM path only; load/parse/inference failures return **loud HTTP errors** and health flags — **no** silent keyword downgrade. **Not in Phase B:** bundled GGUF in repo, preset/advanced discover UI, or manifest/label editing — those are Phase C / pipeline GUI (`treatment_labels`, `trial_manifest.csv`). `/orm/discover` today is **file path discovery only**, not cohort manifest assignment. |
| 2 | **Symlinks** | Reject symlinks whose resolved target escapes the containing allowed root (`sandbox.py`). Lab is **not** using junctions today; policy **does not forbid** links that stay under root. **No** junction-specific tests until lab hardware needs them. |
| 3 | **GUI launcher data root** | Folder dialog default: **session last-used** → else acquisition **output_dir** → user picks. Documented in `local_service_launcher.py`. **v1.1:** persist last successful root in `QSettings` (same pattern as `profile_settings.py`). |
| 4 | **Port 8765** | Fixed default; bind failure surfaces at CLI/GUI spawn. Launcher blocks a second menu spawn while tracked child is alive. **v1.1:** preflight (`GET /orm/health` or socket probe) with clear “port in use” message. |
| 5 | **h5web entry** | **Target:** GUI h5web actions use **long-lived service only** (no second ephemeral Flask). **v1.1 / early C:** change `launch_h5web_for_path` to open `http://127.0.0.1:<port>/?file=<relative>` when health OK; else prompt to start service. |

### v1.1 follow-ups (post–Phase B, not blocking Phase C)

- `QSettings` for `last_orm_data_root`
- Port/health preflight before spawn; surface child stderr on failed start
- Route GUI **Open H5 in h5web** through long-lived service
- Remove dead `except LlmNotConfiguredError: pass` branch in `plan_discover` (control-flow clarity)
- Optional: `skipped_paths` count in discover response for sandbox-filtered globs (observability)

---

## Phase C — Product narrative

**Objective:** Roadmap “single story” — pose → (fit) → apply → overlay → export — with gated features re-enabled safely.

**Agent prompt:** copy-paste from [phase_c_agent_prompt.md](phase_c_agent_prompt.md) when starting Phase C work in a new chat.

### Prerequisites

- Phase A complete (tests, paths, extras)
- Phase B complete (localhost service + launcher); optional v1.1 h5web unification can land in C

### Tasks (ordered)

| ID | Feature | Key files | Menu/UI |
|----|---------|-----------|---------|
| C7 | Observability skeleton | **new** `run_provenance.py`; hooks in sync/workers/fit | JSON logs + git hash |
| C1 | Re-enable Discovery | `menus.py`, `pipeline_dialogs.py` | Remove `setEnabled(False)` on discovery |
| C2 | Virtual acquisition + backend combo | `pipeline_dialogs.py`, `inference_backend.py` | **Done** — menu + `get_backend(kind)` + skip-existing docs |
| C3 | Analyze prefilter UX | `pipeline_dialogs.py`, `trial_filters.py`, `readme.md` | **Done** — `GUI_DEFAULT_PREFILTER_MODE`, dialog + docs |
| C6 | Treatment labels editor | `treatment_labels_csv.py`, `pipeline_dialogs.py` | **Done** — create template + open in OS editor + header validation on sync |
| C4 | kpMS fit GUI worker | `kpms_fit_dialog.py`, `run_kpms_fit` in `fit.py` | **Done** — menu + QThread worker |
| C5 | kpMS apply GUI worker | `kpms_apply_dialog.py`, `run_kpms_apply` in `apply.py` | **Done** — menu + QThread worker |
| C8 | QC at scale (stretch) | `qc_summary.py`, `qc_summary_dialog.py` | **Done** — Pipeline → QC summary… |
| C9 | Overlay menu (optional) | `overlay_dialog.py`, `overlay_run_config.py`, `run_unified_overlay` | **Done** — Pipeline → Render unified overlay… |

### Stays disabled (until preview parity)

| Item | Location |
|------|----------|
| SLEAP trace quality tab | `analysis_settings_dialog.py` tab index 1 |
| DeepLabCut backend | `DeepLabCutBackendStub` |
| kpMS apply confidence fragment filter | commented block in `apply.py` |

### Lab manual checklist

See Phase C subagent report §3 (Discovery sync, inference skip-existing, analyze prefilter, kpMS fit/apply artifacts, treatment CSV, provenance JSON).

### Workflow (decided May 2026)

**Controller-first** for GUI pipeline Discovery: defaults use acquisition `output_dir`, `trials.h5`, and `{animal}_{session}_{trial}.mp4` scan with video-based manifest fallback. Legacy multi-root scans remain available by editing data directories in the dialog; `scripts/legacy_db.py` stays CLI-only.

---

## Phase D — Structural paydown

**Objective:** Maintainability without big-bang rewrite — split `main_window.py` (~2627 lines), quarantine IMPRESS paths, agent docs.

### Prerequisites

- Phase A tests green **before each** extraction PR

### `main_window.py` split (PR order)

1. `legacy_exit_seed.py` (~70 lines, H5 path heuristics)
2. `preview_events.py` (eventFilter)
3. `profile_menu_actions.py`, `pipeline_menu_actions.py`
4. `status_and_config_sync.py`
5. `window_layout.py` (`__init__` UI build)
6. `camera_loop.py` (~750 lines — highest risk; last big chunk)
7. `trial_run_actions.py`

**Target:** `main_window.py` ~500–800 lines; helpers take `window: MainWindow`.

### Scripts classification

| Verdict | Examples |
|---------|----------|
| **Keep** | `legacy_db.py`, overlay scripts, kpms scripts |
| **Promote** → `[project.scripts]` | `reprocess_controller_h5.py`, `export_ram_trial_manifest_csv.py`; use `maze.kpms.fit`/`apply` entrypoints |
| **Archive** | `langfuse_demo.py` → `scripts/demos/` or archive |
| **Frozen** | `scripts/archive/**` (ruff excluded) |

Add `scripts/README.md` (maintained / promoted / archive).

### Deliverables

| Artifact | Path |
|----------|------|
| `AGENTS.md` | repo root (install, paths, tasks, prefilter_mode, testing) |
| Cursor rules | `.cursor/rules/openethomaze-*.mdc` (paths, gui-split, scripts, prefilter) |

### Phase D order after A

1. D1: `AGENTS.md`, `scripts/README.md`, cursor rules
2. D2: IMPRESS path quarantine in `kpms/`, `legacy_db`
3. D3: Script docstrings; archive langfuse demo
4. D4a–f: `main_window` slices (one PR each)
5. D5: Thin CLI promotion to `maze.cli`

---

## Cross-phase dependency summary

| Need | Provider |
|------|----------|
| Committed tests | A1 |
| CI gate | A7 |
| `local-service` extra | A4 / B0 |
| Path sandbox tests | A1 + B7 |
| Safe menu re-enable | A1, A2 |
| GUI subprocess for HTTP | B8 **done**; h5web-via-long-lived → v1.1 / C |
| Long-lived h5web URL | B3 + v1.1 `launch_h5web_for_path` refactor |
| `register_h5web_routes` test | B1 + A1 |
| No IMPRESS in defaults | A2, A3, D2 |

---

## Recommended execution timeline

| Week | Focus | Outcome |
|------|-------|---------|
| 1 | Phase A PR-A1, PR-A2 | Tests exist; paths portable |
| 2 | Phase A PR-A3; start B0–B2 | CI green; sandbox module |
| 3 | Phase B B0–B8 | **Done** — `maze-local-service` + GUI launcher |
| 4 | Phase C C7, C1, C2 | Discovery + inference on |
| 5+ | Phase C C4–C5; Phase D slices | kpMS GUI; smaller main_window |

---

## What we are not doing

- Full stack rewrite (Qt/HDF5/SLEAP/kpMS)
- LLM/YOLO inside Qt process (subprocess only)
- Enabling trace-quality tab before preview parity
- Editing `scripts/archive/` for new features

---

## Next actions (for Agent mode)

1. **Phase C:** use [phase_c_agent_prompt.md](phase_c_agent_prompt.md); resume subagent `dd7ff43b-174c-4ce8-895a-af19af6dc384` if splitting work.
2. Answer open question: **controller-first vs legacy-first** lab workflow (affects C1 Discovery defaults).
3. Optional **Phase B v1.1** slice: unified h5web via long-lived service (decision #5 above).
4. Ethogram: see [ethogram_scope.md](ethogram_scope.md) — **E0** library path can parallel C; **C4/C5** are the GUI face of fit/apply.

---

## Phase E — Ethogram (summary)

Full scope: **[ethogram_scope.md](ethogram_scope.md)**.

- **Not** blocking rescue A–D.
- **Core idea:** slow **fit** (rare) + batch **apply** (repeatable) + cheap **merge/clean/materialize** → bout-level ethogram CSV alongside ambulation metrics.
- **E0 first** (library + tests, no GUI): turns existing `results_apply.h5` into a joinable export.
- **C4/C5** in Phase C are the GUI face of **E1/E2**, not a separate science stack.
