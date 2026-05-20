# Open Etho Maze

Data acquisition and processing for vision-based animal ethology: SLEAP pose tracking, keypoint-MoSeq, and maze metrics (ambulation, exploration bouts, arm entries, object investigations, etc.).

**Inputs:** video and strata labels  
**Outputs:** long-format CSVs of ambulation and exploration metrics

## Prerequisites

- Python **3.12** (managed by [uv](https://docs.astral.sh/uv/))
- Optional lab hardware: Vimba SDK (Allied Vision cameras), jumbo frames if your camera supports them, avrdude for firmware flashing

Install uv (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Install

From the repository root.

**Lean core** (pipeline, HDF5, scripts; no Qt, SLEAP, or local HTTP stack):

```bash
uv sync
```

**Typical lab workstation** (GUI + SLEAP inference + kpMS):

```bash
uv sync --extra gui --extra sleap --extra kpms
```

After changing the `sleap` extra or PyTorch pins, refresh CUDA wheels if needed:

```bash
uv sync --extra gui --extra sleap --extra kpms --reinstall-package torch --reinstall-package torchvision
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda, torch.cuda.device_count())"
```

**Local HTTP service** (waitress, optional LLM/YOLO; Phase B — not required for DAQ-only use):

```bash
uv sync --extra local-service
```

**Development** (pytest, ruff, black, mypy, etc.):

```bash
uv sync --extra dev
```

Combine extras as needed, e.g. `uv sync --extra gui --extra sleap --extra kpms --extra dev`.

Per-machine data roots: copy `maze/pipeline/paths_local.example.py` to `maze/pipeline/paths_local.py` (gitignored) and edit paths.

After editing `pyproject.toml` dependency groups, regenerate the lockfile locally:

```bash
uv lock
uv sync
```

## Run acquisition GUI

From repo root:

```bash
uv run maze-daq
```

Modes:

```bash
uv run maze-daq --vast
uv run maze-daq --ram
uv run maze-ram-daq
```

Requires `--extra gui` (and usually `--extra sleap` for inference menus).

## Demo

![Unified overlay demo](docs/demo_unified_overlay.gif)

![S01T01 unified overlay](docs/demo_1_S01T01_unified_overlay.gif)
