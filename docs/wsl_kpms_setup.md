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
uv sync --extra kpms --extra dev
```

---

## JAX GPU (keypoint-moseq stack)

OpenEthoMaze pins **`jax<0.7`** and **`keypoint-moseq==0.6.3`** (tensorflow_probability compatibility).

Inside **WSL only**, after `uv sync --extra kpms`, install Linux CUDA wheels per [JAX installation](https://docs.jax.dev/en/latest/installation.html):

```bash
# Example — verify versions against pyproject.toml before running
uv pip install "jax[cuda12]"   # or cuda13 per JAX docs; must stay <0.7
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

Streams **blob** and **fused** use separate `--project-dir` subtrees after multi-stream slices ship.

---

## Performance notes

- Reading large HDF5 on `/mnt/d` from WSL is slower than native ext4. For overnight fits, copy cohort to `~/lab-data/` on WSL.
- Three streams (anatomical, blob, fused) ⇒ **three** rare fits — use low `--max-trials` for pilots.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `CpuDevice` only | CUDA jax not installed in **WSL** venv; re-run cuda extra install |
| Manifest paths not found | Translate `D:\` → `/mnt/d/` in CSV or regenerate manifest in WSL |
| kpMS import error | `uv sync --extra kpms` in WSL `.venv` (separate from Windows `.venv`) |
| Slow fit I/O | Move data to WSL native disk or reduce `--max-trials` |
