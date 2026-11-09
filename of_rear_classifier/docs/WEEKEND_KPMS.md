# Per-video CPU kpMS on SuperAnimal OF (Goal B)

**Intent:** fit keypoint-MoSeq (**kpMS**) on SA-TVM pose so syllable bouts become
the labeling unit for rearing (Supported / Unsupported / Grooming / None).

**Design choice:** **one project / model per video**. Syllable ids are **local**
to that recording. No unified cross-session alphabet — we only need bout
boundaries for human labeling, not a shared ethogram.

OEM `maze-kpms-fit` expects maze SLEAP anatomy (`STANDARD_NODE_NAMES`). This OF
path stays under `of_rear_classifier/` until promoted.

## Layout

Canonical root on this box (videos + pose + kpMS moved here):

`D:\Open Field Frailty\`

| Role | Path |
|------|------|
| MP4 | `D:\Open Field Frailty\Open Field - mp4\` |
| SA pose H5 | `D:\Open Field Frailty\Open Field - superanimal\` |
| Per-video kpMS (9-kp, legacy) | `D:\Open Field Frailty\Open Field - kpms_sa_per_video\` |
| Per-video kpMS (**13-kp**, Sturman set) | `D:\Open Field Frailty\Open Field - kpms_sa13_per_video\` |

Other PC historically used `H:\Open Field - …` (same folder names). Legacy 9-kp
cohort: **253** `syllable_bouts.csv`. **Re-fit with 13-kp into a new out-root**
so DOH labels on the 9-kp bout tables stay intact.

## Skeleton (13 keypoints — same as Sturman ReLU)

Source: `parts_map.SA_TVM_PARTS` / `sa_kpms_skeleton.SA_KPMS_BODY_PARTS`

```
nose, head_midpoint, neck, mouse_center,
left_midside, right_midside, left_hip, right_hip,
left_ear, right_ear, tail_base, tail2, tail_end
```

Added vs legacy 9-kp: `head_midpoint`, `left_midside`, `right_midside`, `tail2`.

Anterior / posterior for heading: `nose` / `tail_base`. Edges follow Sturman
S1–S10 length segments (+ ear spokes).

## Defaults

| Knob | Default | Notes |
|------|---------|-------|
| `ar_iters` | 50 | Stage 1 AR-HMM only |
| `full_iters` | 50 | Stage 2 full SLDS |
| `kappa_ar` | 1e8 | Stage-1 stickiness |
| `kappa_full` | 1e4 | Stage-2 bout-length dial |
| `latent_dim` | auto | PCA ≈90% var, floor 4, cap ≈K−1 (≤12 for 13-kp) |
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
  --video "D:\Open Field Frailty\Open Field - mp4\Test 10.mp4" `
  --bouts "D:\Open Field Frailty\Open Field - kpms_sa_per_video\Test 10\model\syllable_bouts.csv" `
  --export-intervals "D:\Open Field Frailty\Open Field - kpms_sa_per_video\Test 10\model\sturman_intervals.csv"
```

## Re-fit — 13-kp Sturman skeleton (this box)

Writes a **new** tree so legacy 9-kp projects + DOH labels stay readable.

```powershell
cd C:\Users\admin\code\OpenEthoMaze
# once: uv sync --extra kpms

# smoke one short video first
uv run --extra kpms python of_rear_classifier/scripts/fit_sa_cohort_kpms_cpu.py `
  --h5-dir "D:\Open Field Frailty\Open Field - superanimal" `
  --out-root "D:\Open Field Frailty\Open Field - kpms_sa13_per_video" `
  --only "Test 10" `
  --ar-iters 10 `
  --full-iters 10 `
  --save-every 10 `
  --no-skip-existing

# labeling set (then expand / full cohort)
uv run --extra kpms python of_rear_classifier/scripts/fit_sa_cohort_kpms_cpu.py `
  --h5-dir "D:\Open Field Frailty\Open Field - superanimal" `
  --out-root "D:\Open Field Frailty\Open Field - kpms_sa13_per_video" `
  --only "Test 10" "Test 42" "Test 77" "Test 111" "Test 222" `
  --ar-iters 50 `
  --full-iters 50 `
  --save-every 25 `
  --workers 8
```

Syllable ids / bout tables are **not** comparable to the 9-kp run — re-label on
the new `syllable_bouts.csv` (or keep DOH 9-kp labels only for the old transfer
study).

## Goal B labeling (next)

**Chosen set (pseudo-random):** Tests **42, 77, 111, 222** (all have mp4 +
`syllable_bouts.csv`). Optional warm-up: short **Test 10**.

Do **not** label every bout (~900–1200 each). Scrub + mark clear intervals.

```powershell
cd C:\Users\admin\code\OpenEthoMaze
# once: uv sync --extra gui    # PySide6 (user runs install)

$id = 42   # then 77, 111, 222
uv run python of_rear_classifier/scripts/label_syllable_bouts.py `
  --video "D:\Open Field Frailty\Open Field - mp4\Test $id.mp4" `
  --bouts "D:\Open Field Frailty\Open Field - kpms_sa13_per_video\Test $id\model\syllable_bouts.csv" `
  --scorer YourInitials
```

Or launch with **no args** → file pickers + scorer dialog.

**App UI (PySide6):** on-screen keymap · **overview + detail** timeline
(whole-session navigator with yellow viewport box; detail shows ~45 s by
default — wheel pan, Ctrl+wheel zoom) · Open video / Open bouts · scorer box.
Space plays the active bout (buttons cannot steal it).

| Key | Action |
|-----|--------|
| `1`/`2`/`3`/`0`/`n` | Supported / Unsupported / Grooming / None |
| `a`/`d` | prev / next bout |
| `space` | play bout |
| `[` / `]` | manual start / end frame (for rear split across 2 syllables) |
| `c` / `Esc` | clear pending manual range (**Esc does not quit**) |
| `s` | save · `e` export Sturman intervals · `q` quit |

Per-scorer files (collaborator-safe):  
`…\Test N\model\labels\<scorer>.csv`  
plus `…\labels\<scorer>_sturman_intervals.csv` on `e`.

**Workflow tip:** scrub hypnogram; for a rear that spans two kpMS syllables set
`[` at true onset, `]` at offset, then `1`/`2`. Leave uncertain unlabeled.

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
