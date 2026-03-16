# vast-controller

Circular open field rodent behavior controller (warmer/colder vibration task).

## Run

From repo root (with [uv](https://github.com/astral-sh/uv)):

```powershell
uv run python -m vast_controller
```

Or after install (`uv sync` / `pip install -e .`):

```powershell
vast-controller
```

Optional: `--debug-log` to enable DEBUG-level messages in the log file.

**Run analysis after each trial:** In the Run section you can enable "Run analysis after each trial". When on, the controller runs the VAST pipeline (heatmap, movement bouts, summary) for each trial as it completes. This requires `vast_pipeline` to be importable (e.g. add the VAST repo to `PYTHONPATH` or install it). If `vast_pipeline` is not available, the status bar will show an error after the trial.

## Project structure

```
vast_controller/
├── pyproject.toml          # deps, [project.scripts] → vast-controller
├── vast_controller/         # main package
│   ├── __main__.py         # entry point (main, argparse)
│   ├── gui/                # Qt main window, settings
│   ├── h5web_server.py     # local h5web + h5grove server
│   ├── config.py, profile.py, trial_logic.py, ...
│   └── ...
├── web/
│   ├── h5web/              # React h5web app (build with Node)
│   └── h5web_dist/         # built static files (served by app)
├── scripts/
│   └── install.ps1         # install/update on target machines
├── docs/
├── profiles/
└── tests/
```

## Install on target machines

**Prerequisites (once per machine):**

- Python ≥ 3.12  
- [uv](https://github.com/astral-sh/uv) (`pip install uv`)  
- Vimba SDK (Allied Vision), CUDA (if using SLEAP) — install per vendor.

**Option A — clone then run install script:**

```powershell
git clone <repo-url> C:\vast_controller
cd C:\vast_controller
.\scripts\install.ps1
```

To create a desktop shortcut:

```powershell
.\scripts\install.ps1 -CreateShortcut
```

To include SLEAP extra (then add CUDA wheels as below):

```powershell
.\scripts\install.ps1 -Sleap -CreateShortcut
```

**Option B — manual:** `cd` to repo, then `uv sync --extra gui` (and `sleap` if needed). Run with `uv run python -m vast_controller`.

**H5Web viewer:** Ensure `web/h5web_dist/` exists (build once with `cd web/h5web && npm run build` and commit, or copy from another machine). The install script does not run Node.

## SLEAP + CUDA

The `sleap` extra uses `sleap-nn[torch-cuda130]`. After `uv sync --extra sleap`, install the CUDA builds so SLEAP sees CUDA:

```powershell
uv pip install torch torchvision --default-index https://download.pytorch.org/whl/cu130 --reinstall
```

Re-run that after any later `uv sync` if the lockfile resets to CPU torch.

## Dev

```powershell
uv run ruff check vast_controller tests --select F401,F841 --fix
uv run vulture vast_controller
```
