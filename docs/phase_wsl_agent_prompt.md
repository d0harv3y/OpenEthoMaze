# Phase WSL agent prompt (copy into a new Cursor chat)

Cross-OS workflow for **Windows acquisition + WSL2 GPU kpMS fit**. Master plan: [tracking_kpms_master_plan.md](tracking_kpms_master_plan.md).

---

## Cursor / workspace strategy (read first)

### What **not** to do

- **Do not** add `\\wsl.localhost\archlinux\home\admin\code\OpenEthoMaze` as a folder in a **Windows-hosted** Cursor workspace. Cursor warns correctly: LSP, file watchers, and I/O are slow; some features break.
- **Do not** edit the same file concurrently from Windows Cursor and WSL Cursor without saving/syncing — last writer wins.

### Recommended patterns (pick one)

#### Pattern A — Single tree on `/mnt/c` (simplest; one workspace)

| Role | How |
|------|-----|
| Code canonical | `C:\Users\admin\code\OpenEthoMaze` |
| WSL access | `cd /mnt/c/Users/admin/code/OpenEthoMaze` |
| Cursor | **One** window: open the **Windows** path `C:\Users\admin\code\OpenEthoMaze` |
| Fit terminal | Integrated terminal profile **WSL** → `cd /mnt/c/Users/admin/code/OpenEthoMaze` → `uv run maze-kpms-fit ...` |
| venvs | `.venv` Windows (GUI) + separate `.venv` inside WSL at same path (gitignored) |

**Pros:** One git tree, visible in your current Windows workspace, no duplicate commits.  
**Cons:** Slower HDF5 I/O on `/mnt/d` data from WSL; acceptable for pilot fits, copy cohort to `~/lab-data` for overnight runs if needed.

#### Pattern B — WSL-native editor for fit work (best Linux I/O)

| Role | How |
|------|-----|
| Cursor | Command Palette → **WSL: Reopen Folder in WSL** → open `/home/admin/code/OpenEthoMaze` |
| Windows GUI | **Second** Cursor window on `C:\Users\admin\code\OpenEthoMaze` **only if** trees stay synced |

**Requires sync rule:** two clones must `git pull` before switching OS, or use **symlink** in WSL:

```bash
# In WSL — point at Windows tree (Pattern A symlink variant)
rm -rf ~/code/OpenEthoMaze   # only if duplicate clone — backup first
ln -s /mnt/c/Users/admin/code/OpenEthoMaze ~/code/OpenEthoMaze
```

Then **Reopen in WSL** on `~/code/OpenEthoMaze` still uses the Windows files.

#### Pattern C — Two clones + git sync (performance purist)

| Clone | Path | Use |
|-------|------|-----|
| Windows | `C:\Users\admin\code\OpenEthoMaze` | DAQ, daily dev |
| WSL native | `~/code/OpenEthoMaze` on ext4 | Overnight GPU fit |

**Rule:** `git pull` on both before/after fit sessions; never long-lived uncommitted drift on one side.

**Not one workspace** — two Cursor windows, explicit sync discipline.

### Multi-root workspace?

Avoid a `.code-workspace` with both `C:\...\OpenEthoMaze` and `\\wsl$\...\OpenEthoMaze` — that is two copies of the repo in one UI and invites confusion. Prefer Pattern A + WSL terminal.

### Visibility from Windows workspace while fitting in WSL

You do **not** need the WSL path in the Windows workspace file list. Terminal output and git commits on the shared `/mnt/c` tree are enough. Artifacts (`fit_summary.json`, checkpoints) appear under the Windows path immediately.

---

## Prompt — W0 WSL docs + path examples

```
Scope: W0 only (docs/phase_wsl_agent_prompt.md).

Add operational docs for WSL2 kpMS GPU fit — no science code changes.

Deliverables:
- docs/wsl_kpms_setup.md: NVIDIA driver, wsl nvidia-smi, uv sync --extra kpms, jax<0.7 CUDA install inside WSL, verify jax.devices()
- maze/pipeline/paths_local.wsl.example.py: DATA_DIR=/mnt/d/... pattern
- Link from tracking_kpms_master_plan.md and AGENTS.md § Cross-OS

Document Pattern A (single /mnt/c tree) as default for this lab.

Out of scope: T0–T4 code, pyproject jax pin changes unless required for docs accuracy.

Acceptance: human can follow doc on fresh WSL shell; no E:\ in maze/ defaults.
```

---

## Prompt — W1 GPU verify + fit guard

```
Scope: W1 only. Prerequisites: W0, T2b (H5 pose readable).

Deliverables:
- scripts/wsl_verify_jax_gpu.sh (or maze/cli/verify_jax_gpu.py): print jax version, devices, backend; exit 1 if CPU-only when MAZE_REQUIRE_GPU=1
- maze/kpms/fit.py: at start of run_kpms_fit, log warning if jax.default_backend() is cpu (once per run)
- tests/test_verify_jax_gpu.py: mock jax, no GPU in CI

Register script in scripts/README.md; optional [project.scripts] maze-verify-jax-gpu.

Out of scope: auto-install CUDA wheels in pyproject.

Acceptance: CI passes without GPU; script runs in WSL manually.
```

---

## WSL fit SOP (operator)

After T2b + W0:

```bash
# WSL terminal — Pattern A
cd /mnt/c/Users/admin/code/OpenEthoMaze
uv sync --extra kpms --extra dev
# Install CUDA jax per docs/wsl_kpms_setup.md (jax<0.7 for keypoint-moseq)
uv run python -c "import jax; print(jax.devices())"

export MAZE_DATA_ROOT=/mnt/d/scratch   # if using env resolver

uv run maze-kpms-fit \
  --project-dir /mnt/d/scratch/kpms/anatomical \
  --manifest-csv /mnt/d/scratch/trial_manifest.csv \
  --max-trials 50 \
  --pose-stream anatomical   # after T4c
```

Repeat for `--pose-stream blob` and `fused` only after T4a/T4b — **3× fit cost**.

---

## Path translation cheat sheet

| Windows | WSL |
|---------|-----|
| `C:\Users\admin\code\OpenEthoMaze` | `/mnt/c/Users/admin/code/OpenEthoMaze` |
| `D:\scratch\trials.h5` | `/mnt/d/scratch/trials.h5` |
| `D:\work sack\vibration maze` | `/mnt/d/work sack/vibration maze` |

Manifest CSVs used for WSL fit should use **WSL paths** or **relative paths** from a declared `--data-root` (implement in T2c if not done).

---

## JAX on Windows vs WSL (June 2026)

| Environment | GPU |
|-------------|-----|
| Native Windows | **CPU only** (official) |
| WSL2 + NVIDIA driver | **CUDA experimental** — use Linux `jax[cuda12]` or `jax[cuda13]` wheels still **jax 0.6.x** for keypoint-moseq 0.6.3 |

Do not expect native Windows CUDA jax for this stack.
