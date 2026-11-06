# of_rear_classifier

Sturman / SuperAnimal open-field **rearing MLP** pilot (Supported / Unsupported /
Grooming / None). Seed of a future extractable OF frailty tree — **not** OEM DAQ
library code.

Design dictionary: [`docs/data_dictionaries/INFO_of_rear_classifier.md`](../docs/data_dictionaries/INFO_of_rear_classifier.md).

## Isolation contract

| May import | Must not import |
|------------|-----------------|
| `maze.pipeline.open_field.dlc_h5` | `maze.controller.*` |
| `maze.pipeline.open_field.floor_quad` (fit helpers only if needed) | acquisition GUI, local-service, kpMS |
| stdlib / numpy / pandas / (optional) torch | geometric `rear_proxy_*` as training labels |

Skeleton features, windowing, MLP, labels, bout post-process, and train/eval live
**here**. Do not grow rearing MLP into `maze/pipeline/open_field`.

Geometric Parks #7 proxy remains interim in maze; this root owns the classifier path.

Archival MoSeq pilots: [`moseq-mountain/`](../moseq-mountain/).

## Layout

```text
of_rear_classifier/          # this root (repo child)
  of_rear_classifier/        # importable package
  tests/
  scripts/                   # CLIs later
  README.md
```

## Run (OEM uv env)

From OpenEthoMaze repo root (`pythonpath` includes `of_rear_classifier/`):

```powershell
uv run pytest of_rear_classifier/tests -q
# package root must be on path (pytest.ini already sets pythonpath):
uv run python -c "import sys; sys.path.insert(0, 'of_rear_classifier'); from of_rear_classifier.skeleton import FEATURE_NAMES; print(len(FEATURE_NAMES))"
```

H5 smoke:

```powershell
uv run python of_rear_classifier/scripts/smoke_h5.py `
  --h5 "D:\Open Field - superanimal\Test 27_superanimal_topviewmouse_….h5" `
  --quad-csv "D:\DeepLabCut\of_frailty\floor_quads\floor_quads.csv" `
  --max-frames 300
```

## Goal A — Sturman LOOCV

```powershell
uv run --extra sleap python of_rear_classifier/scripts/run_sturman_loocv.py `
  --oft-root "C:\Users\admin\code\DLCAnalyzer\data\OFT" `
  --out-dir of_rear_classifier/runs/sturman_loocv
```

Writes `fold_metrics.csv` + `summary.json` (20 videos × Jin/Furkan/Oliver).
Needs torch (`--extra sleap` or lab). See INFO for numbers.

## Status / goals

Ladder (full text in INFO): **A** Sturman LOOCV ✓ → **B** Davis transfer (2–5
labeled vids) → **C** FI `rear_ml_*` → **D** optional multi-rater dense.

Goal A complete. Goal B: **per-video CPU kpMS** (no shared alphabet) + matplotlib
labeler — see [docs/WEEKEND_KPMS.md](docs/WEEKEND_KPMS.md). Full SA H5 cohort on
`H:\` (mirrors `D:\`); pilot Test 10 locally first.

```powershell
# Per-video CPU fit (pilot: Test 10, short iters)
uv run --extra kpms python of_rear_classifier/scripts/fit_sa_cohort_kpms_cpu.py `
  --h5-dir "D:\Open Field - superanimal" `
  --out-root "D:\Open Field - kpms_sa_per_video" `
  --only "Test 10" --ar-iters 10 --full-iters 10 --save-every 10

# Labeler (matplotlib; OEM opencv is often GUI:NONE)
uv run python of_rear_classifier/scripts/label_syllable_bouts.py `
  --video "D:\Open Field - mp4\Test 10.mp4" `
  --bouts "D:\Open Field - kpms_sa_per_video\Test 10\model\syllable_bouts.csv"

# Full cohort on other PC (after commit/pull) — 128 GB: start --workers 8–12
uv run --extra kpms python of_rear_classifier/scripts/fit_sa_cohort_kpms_cpu.py `
  --h5-dir "H:\Open Field - superanimal" `
  --out-root "H:\Open Field - kpms_sa_per_video" `
  --workers 12
```

