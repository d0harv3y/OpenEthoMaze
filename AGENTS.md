# Agent guide — OpenEthoMaze

Concise map for Cursor agents working on this repo. Master plan: [docs/rescue_plan.md](docs/rescue_plan.md). Phase prompts: [docs/phase_c_agent_prompt.md](docs/phase_c_agent_prompt.md), [docs/phase_d_agent_prompt.md](docs/phase_d_agent_prompt.md).

## Install (uv)

From repo root. Do not `pip install` ad hoc — declare extras in `pyproject.toml` and `uv sync`.

| Goal | Command |
|------|---------|
| Lean core (HDF5, pipeline, CLI) | `uv sync` |
| Lab workstation (GUI + SLEAP + kpMS) | `uv sync --extra gui --extra sleap --extra kpms` |
| Local ORM HTTP service | `uv sync --extra local-service` |
| Development / CI | `uv sync --extra dev` |
| Everything | `uv sync --extra lab` (meta: gui, sleap, local-service, kpms, dev) |

After dependency changes: `uv lock` then `uv sync`.

## Paths (portable defaults)

- **Library defaults:** [maze/pipeline/paths.py](maze/pipeline/paths.py) — repo-relative; no lab drive letters in `maze/` code.
- **Per machine:** copy [maze/pipeline/paths_local.example.py](maze/pipeline/paths_local.example.py) → `maze/pipeline/paths_local.py` (gitignored). Set `DATA_DIR` / `DATA_DIRS`, optional `OUTPUT_H5`, optional `DISCOVERY_PROFILE`.
- **Env (local service):** `MAZE_LLM_GGUF`, `MAZE_YOLO_WEIGHTS`, `MAZE_YOLO_WEIGHTS_DIR` — see [readme.md](readme.md).
- **Do not** add `E:\`, IMPRESS, or other lab-specific paths as defaults in `maze/` (Phase D2).

## Acquisition GUI

Entry: `uv run maze-daq` (needs `--extra gui`). Composition root: [maze/controller/acquisition/gui/main_window.py](maze/controller/acquisition/gui/main_window.py) (~2600 lines; Phase D4 splits into `gui/*_*.py` helpers).

| Area | Module |
|------|--------|
| Menus / actions wiring | [menus.py](maze/controller/acquisition/gui/menus.py) |
| Pipeline dialogs (discovery, virtual acq, analyze) | [pipeline_dialogs.py](maze/controller/acquisition/gui/pipeline_dialogs.py) |
| kpMS fit / apply | [kpms_fit_dialog.py](maze/controller/acquisition/gui/kpms_fit_dialog.py), [kpms_apply_dialog.py](maze/controller/acquisition/gui/kpms_apply_dialog.py) |
| QC summary, overlay render | [qc_summary_dialog.py](maze/controller/acquisition/gui/qc_summary_dialog.py), [overlay_dialog.py](maze/controller/acquisition/gui/overlay_dialog.py) |
| File / H5 / h5web | [file_actions.py](maze/controller/acquisition/gui/file_actions.py) |

**Local service:** File → Start local ORM service… spawns `maze-local-service` subprocess (`--extra local-service`). LLM/YOLO stay out of the Qt process.

**Out of scope in GUI:** DeepLabCut backend, SLEAP trace-quality tab, in-process LLM/YOLO (see rescue_plan).

## Pipeline menu ↔ behavior

| Menu | `prefilter_mode` / notes |
|------|--------------------------|
| **Analyze…** | `controller` (GUI default) — [trial_filters.py](maze/pipeline/trial_filters.py) `GUI_DEFAULT_PREFILTER_MODE` |
| **Virtual acquisition…** | SLEAP-NN batch; skip-existing when pose sidecar already present |
| **Discovery…** | Scans output folder; `treatment_labels.csv` editor (not HTTP discover) |
| Legacy batch CLI | `uv run maze-legacy-db run` uses `prefilter_mode=legacy` |

Modes: `controller` (no legacy frame-diff / mistrial gates), `legacy` (strict), `auto` (infer from manifest). Details: [readme.md](readme.md) § Analyze prefilter modes.

## Testing & lint

```bash
uv sync --extra dev
uv run ruff check maze tests
uv run black --check .
uv run pytest tests/ -q
```

- `pythonpath = ["tests", "."]` in `pyproject.toml`.
- Controller HTTP fixtures: `pytest_plugins = ["controller.local_service.fixtures"]` in tests that need them — **not** `tests.*` (site-packages may shadow `tests/`).
- Focused run: `uv run pytest tests/test_foo.py -q`
- Optional integration markers: `llm_integration`, `yolo_integration` (need local-service extra + env).

Run `uv run pytest tests/ -q` **before and after** each Phase D4 `main_window` extraction; no scientific behavior changes when moving GUI code.

## CLI & scripts

- Implement batch tools in [maze/cli/](maze/cli/); expose via `[project.scripts]` in `pyproject.toml`.
- [scripts/README.md](scripts/README.md) — console commands and maintained / promoted / archive classification.
- Prefer `uv run maze-<name>` over `uv run python scripts/<name>.py` (shims delegate to `maze.cli`).

## What not to edit

| Path | Reason |
|------|--------|
| `scripts/archive/**` | Frozen legacy; ruff/black excluded — no new features |
| `maze/pipeline/paths_local.py` | Gitignored per-machine; use example + env/CLI |
| Phase E ethogram GUI | [docs/ethogram_scope.md](docs/ethogram_scope.md) — parallel track |

## Phase status (short)

- **A–C:** Shipped (tests, paths, CI, `maze-local-service`, pipeline menus, kpMS/QC/overlay).
- **D (in progress):** D1 docs/rules → D2 paths → D3 scripts → D4a–g `main_window` slices → D5 CLI promotion.
- **E:** Ethogram materialize/fit — library path can start without GUI.

Commit only when the user asks.
