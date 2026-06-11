# WSL2 + GPU setup for kpMS fit

Operational guide for running **`maze-kpms-fit`** with JAX on GPU inside WSL2, while keeping **maze-daq** on native Windows.

**Related:** [tracking_kpms_master_plan.md](tracking_kpms_master_plan.md), [phase_wsl_agent_prompt.md](phase_wsl_agent_prompt.md), [h5_tracking_contract.md](h5_tracking_contract.md).

---

## Workspace model (default: Pattern A)

Use **one git tree** on the Windows filesystem:

| Side | Path |
|------|------|
| Windows | `C:\Users\admin\code\OpenEthoMaze` |
| WSL | `/mnt/c/Users/admin/code/OpenEthoMaze` |

Open **one** Cursor window on the Windows path. Run fit commands in a **WSL** integrated terminal.

Do **not** open `\\wsl.localhost\...` from Windows Cursor for daily editing (slow, incomplete IDE support).

If you created a duplicate clone under `~/code/OpenEthoMaze` in WSL, prefer a symlink to `/mnt/c/...` or sync via `git` — see [phase_wsl_agent_prompt.md](phase_wsl_agent_prompt.md).

---

## Prerequisites

1. **Windows:** NVIDIA driver with WSL support (recent Studio or Game Ready).
2. **WSL2:** Arch/Ubuntu with `nvidia-smi` working inside WSL.
3. **Python 3.12** via [uv](https://docs.astral.sh/uv/) in WSL.

```bash
cd /mnt/c/Users/admin/code/OpenEthoMaze
# Use a Linux-native .venv (do not reuse a Windows-created .venv on /mnt/c/...).
uv sync --extra kpms --extra dev
```

`pyproject.toml` selects **Linux-only** wheels when you run `uv sync` inside WSL:

| Package | Linux (WSL) | Windows |
|---------|-------------|---------|
| OpenCV | `opencv-python-headless` (no `libGL.so.1`) | `opencv-python` |
| JAX (kpms extra) | `jax[cuda12]<0.7` | `jax` + `jaxlib` CPU |

After dependency changes on either OS: `uv lock` then re-run `uv sync` **on that OS**.

---

## JAX GPU (keypoint-moseq stack)

OpenEthoMaze pins **`jax<0.7`** and **`keypoint-moseq==0.6.3`** (tensorflow_probability compatibility).

On **WSL/Linux**, `uv sync --extra kpms` should install **`jax[cuda12]<0.7`** automatically. If you still see CPU-only JAX, reinstall the extra:

```bash
uv sync --extra kpms --reinstall-package jax --reinstall-package jaxlib
```

Verify:

```bash
uv run python -c "import jax; print(jax.__version__, jax.devices(), jax.default_backend())"
# Expect CudaDevice(...) and backend gpu
```

**Native Windows:** CPU-only for JAX — do not expect GPU fit on Windows host.

---

## Per-machine paths in WSL

```bash
cp maze/pipeline/paths_local.wsl.example.py maze/pipeline/paths_local.py
# edit /mnt/d/... paths
```

Manifest CSV paths used for fit must be valid **inside WSL** (`/mnt/d/...` not `D:\...`).

---

## Pilot fit (after Tracking T2 + T4c)

```bash
cd /mnt/c/Users/admin/code/OpenEthoMaze
uv run maze-kpms-fit \
  --project-dir /mnt/d/scratch/kpms/anatomical \
  --manifest-csv /mnt/d/scratch/trial_manifest.csv \
  --max-trials 50
```

Streams **blob** and **fused** land under `<project-dir>/<pose_stream>/` (see `maze.kpms.project_paths`).

### Multi-stream / multi-seed sweep (WSL GPU box)

From repo root on a native WSL clone (e.g. MED-DavisData2 at `/home/code/OpenEthoMaze`):

```bash
cd /home/code/OpenEthoMaze
bash scripts/wsl_kpms_multi_stream_fit_sweep.sh
```

Default: **anatomical**, **blob**, **fused** × seeds **5, 13, 42, 67, 111** →  
`/home/data/test/<stream>/seed_<NNN>/` (80 trials, stratified balance, `--force-new`).  
Logs: `/home/data/test/fit_logs/`. Override paths via `KPMS_PROJECT_DIR`, `KPMS_MANIFEST`, etc. (see script header).

---

## Performance notes

- Reading large HDF5 on `/mnt/d` from WSL is slower than native ext4. For overnight fits, copy cohort to `~/lab-data/` on WSL.
- Three streams (anatomical, blob, fused) ⇒ **three** rare fits — use low `--max-trials` for pilots.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `libGL.so.1: cannot open shared object file` | Run `uv sync` **inside WSL** (headless OpenCV is Linux-only in pyproject); do not reuse Windows `.venv` |
| `CpuDevice` only | `nvidia-smi` in WSL; then `uv sync --extra kpms --reinstall-package jax --reinstall-package jaxlib` |
| Manifest paths not found | Translate `D:\` → `/mnt/d/` in CSV or regenerate manifest in WSL |
| kpMS import error | `uv sync --extra kpms` in WSL `.venv` (separate from Windows `.venv`) |
| Slow fit I/O | Move data to WSL native disk or reduce `--max-trials` |
