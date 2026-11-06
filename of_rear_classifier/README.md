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

## Status

Scaffold + 22-D skeleton / window litmus. MLP train and Sturman LOOCV = follow-on.
