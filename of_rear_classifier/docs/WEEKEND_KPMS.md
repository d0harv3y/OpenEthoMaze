# Per-video CPU kpMS on SuperAnimal OF (Goal B)

**Intent:** fit keypoint-MoSeq (**kpMS**) on SA-TVM pose so syllable bouts become
the labeling unit for rearing (Supported / Unsupported / Grooming / None).

**Design choice:** **one project / model per video**. Syllable ids are **local**
to that recording. No unified cross-session alphabet — we only need bout
boundaries for human labeling, not a shared ethogram.

OEM `maze-kpms-fit` expects maze SLEAP anatomy (`STANDARD_NODE_NAMES`). This OF
path stays under `of_rear_classifier/` until promoted.

## Layout (D:\ ↔ H:\ mirror)

| Role | This machine | Other PC |
|------|--------------|----------|
| SA pose H5 | `D:\Open Field - superanimal\` | `H:\Open Field - superanimal\` |
| MP4 | `D:\Open Field - mp4\` | `H:\Open Field - mp4\` |
| Per-video kpMS out | `D:\Open Field - kpms_sa_per_video\` | `H:\Open Field - kpms_sa_per_video\` |

This box currently has a **subset** of SA H5s (incl. Test 10). Full cohort lives
on the other machine under `H:\`.

## Skeleton (9 keypoints)

`nose, left_ear, right_ear, neck, mouse_center, left_hip, right_hip, tail_base, tail_end`

Anterior / posterior for heading: `nose` / `tail_base`.

## Defaults

| Knob | Default | Notes |
|------|---------|-------|
| `ar_iters` | 50 | Stage 1 AR-HMM only |
| `full_iters` | 50 | Stage 2 full SLDS |
| `kappa_ar` | 1e8 | Stage-1 stickiness |
| `kappa_full` | 1e4 | Stage-2 bout-length dial |
| `latent_dim` | auto | PCA ≈90% var, capped at 8 |
| device | CPU / JAX | `parallel_message_passing=False` |
| noise_calibration | skipped | uses config defaults (batch-safe) |

Outputs per video:

```text
<out-root>/<recording_id>/
  config.yml
  pca.p
  model/
    checkpoint_*.p
    results.h5
    syllable_bouts.csv
    fit_summary.json
```

Bout CSV: `bout_index, syllable_id, t0_frame, t1_frame, n_frames, label`

## Local pilot — Test 10 (✓ 2026-11-06)

Test 10 is the shorter OF clip (~10 min / ~18k frames; H5 ~11 MB vs ~22 MB).
Short-iter smoke (**10+10**) finished in **~26 s** on this CPU box →
`359` bouts, `30` syllable ids, `syllable_bouts.csv` written. Production
should use **50+50** (and default `latent_dim` floor 4).

```powershell
cd C:\Users\admin\code\OpenEthoMaze

# Needs: uv sync --extra kpms   (user runs install)

uv run --extra kpms python of_rear_classifier/scripts/fit_sa_cohort_kpms_cpu.py `
  --h5-dir "D:\Open Field - superanimal" `
  --out-root "D:\Open Field - kpms_sa_per_video" `
  --only "Test 10" `
  --ar-iters 10 `
  --full-iters 10 `
  --save-every 10 `
  --no-skip-existing

# Labeler (matplotlib — OEM opencv is often GUI:NONE)
uv run python of_rear_classifier/scripts/label_syllable_bouts.py `
  --video "D:\Open Field - mp4\Test 10.mp4" `
  --bouts "D:\Open Field - kpms_sa_per_video\Test 10\model\syllable_bouts.csv"
```

## Full cohort — other PC (H:\)

After this repo is committed + pulled:

```powershell
cd C:\Users\admin\code\OpenEthoMaze
# uv sync --extra kpms   # once, if needed

uv run --extra kpms python of_rear_classifier/scripts/fit_sa_cohort_kpms_cpu.py `
  --h5-dir "H:\Open Field - superanimal" `
  --out-root "H:\Open Field - kpms_sa_per_video" `
  --ar-iters 50 `
  --full-iters 50 `
  --save-every 25 `
  --workers 12
```

- `--skip-existing` is **on by default** (resume-safe).
- Failures are logged per video; cohort continues.
- Manifest: `H:\Open Field - kpms_sa_per_video\cohort_manifest.json`

### Concurrency (`--workers`) on 128 GB RAM

Measured on this box (JAX CPU): **~1.3 GB peak RSS** for Test 10 (~10 min /
18k frames, `latent_dim=4`). A **~20 min** clip (~36k frames) is roughly
**~2–3 GB** working set; budget **~4 GB/worker** with headroom for spikes + OS.

| Workers | Rough RAM | Guidance |
|---------|-----------|----------|
| **8–12** | ~32–50 GB | **Start here** on 128 GB |
| 16 | ~64 GB | Fine if CPU cores ≥ ~32 and disk keeps up |
| 24–32 | ~96–128 GB | RAM-feasible; often **CPU/disk bound** / thrash |

Also leave ~16–32 GB free for Windows + H: cache. Each worker pins
`OMP/MKL/OPENBLAS_NUM_THREADS=1` so processes don't oversubscribe BLAS.

Watch Task Manager: if RAM >~100 GB or CPU stuck at 100% with falling
throughput, drop `--workers`. Disk (many concurrent H5/checkpoint writes)
is the usual second bottleneck after RAM.

Single-video CLI: `of_rear_classifier/scripts/fit_sa_video_kpms_cpu.py`.

## Labeler keys

`1` Supported · `2` Unsupported · `3` Grooming · `0`/`n` None · `a`/`d` prev/next ·
`space` play · `s` save · `q` quit. Focus the **matplotlib** window for keys.

## Optional: npz export only

```powershell
uv run python of_rear_classifier/scripts/export_sa_for_kpms.py `
  --h5-dir "D:\Open Field - superanimal" `
  --out-dir "D:\Open Field - kpms_sa_export" `
  --likelihood-min 0.3
```

Not required for the CPU fit scripts above (they read H5 directly).
