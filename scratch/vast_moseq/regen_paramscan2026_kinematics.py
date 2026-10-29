"""Bout kinematics for az-sd-vast_paramscan2026 anatomical paramscan fits.

Reuses VAST run-phase bout scalars (spot / heading / nose–tail) from
``regen_syllable_bout_kinematics.build_trial_rows``, pointed at this ensemble.

Default cohort: drop ``ct=0.1`` (18 models = k2 × K × {0.2, 0.3}).

Regen (OpenEthoMaze repo root):

  uv run python scratch/vast_moseq/regen_paramscan2026_kinematics.py
  uv run python scratch/vast_moseq/regen_paramscan2026_kinematics.py --max-trials 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import h5py
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
_REPO = _SCRATCH.parent
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from maze.kpms.behavior_ethogram.bout_scalars import (  # noqa: E402
    DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
)
from maze.kpms.frame_alignment import KpmsAlignmentCache, kpms_recording_key  # noqa: E402
from maze.kpms.preprocess import KpmsPreprocessConfig  # noqa: E402
from maze.pipeline.io.file_discovery import load_manifest_csv  # noqa: E402
from vast_moseq.regen_syllable_bout_kinematics import (  # noqa: E402
    KINEMATICS_FIELDS,
    _append_csv_rows,
    _write_csv_header,
    build_trial_rows,
)

DEFAULT_ENSEMBLE = Path(r"D:\az-sd-vast_paramscan2026\anatomical")
DEFAULT_MANIFEST = Path(r"D:\az-sd-vast_paramscan2026\gerstner_trial_manifest_kpms_fit.csv")
DEFAULT_TRACKING = Path(r"D:\az-sd-vast_paramscan2026\vast_results_legacy.h5")
DEFAULT_OUT = Path(r"D:\az-sd-vast_paramscan2026\_syllable_bout_kinematics")

_MODEL_RE = re.compile(
    r"^paramscan_s1-([^_]+)_s2-([^_]+)_ss-(\d+)(?:_ct-([0-9.eE+-]+))?$"
)


def parse_model(name: str) -> dict[str, object]:
    m = _MODEL_RE.match(name)
    if m is None:
        raise ValueError(f"unrecognized model name: {name!r}")
    return {
        "model": name,
        "kappa1": m.group(1),
        "kappa2": m.group(2),
        "ss": int(m.group(3)),
        "ct": m.group(4) if m.group(4) is not None else "",
        "ct_f": float(m.group(4)) if m.group(4) is not None else 0.2,
    }


def discover_models(ensemble: Path, *, exclude_ct: set[str]) -> list[str]:
    names: list[str] = []
    for p in sorted(ensemble.glob("paramscan_*")):
        if not (p.is_dir() and (p / "results.h5").is_file()):
            continue
        meta = parse_model(p.name)
        if str(meta["ct"]) in exclude_ct:
            continue
        names.append(p.name)
    return names


def _info_md(*, exclude_ct: list[str], n_models: int) -> str:
    return f"""# INFO — paramscan2026 syllable bout kinematics

Grain: one row = one kpMS syllable bout × model, **run-phase only** (majority
``trial_state`` = ``run``).

## Cohort

| Source | Role |
|--------|------|
| `anatomical/paramscan_*/results.h5` | {n_models} alphabets (dropped ct: {exclude_ct or "none"}) |
| `vast_results_legacy.h5` | Anatomical pose (spot / nose–tail); feedback `trial_state` |
| `gerstner_trial_manifest_kpms_fit.csv` | Trial join keys (~1993 used / model) |

Habituation keys (`*-hS*-T*`) are included when present in `results.h5`.

## Spot / heading

- **Spot** = mean(nose, neck, spine)
- **Heading** = kpMS `heading`
- **Nose–tail** = Euclidean nose→tail (m)
- Object-distance columns = NaN (no fam/nvl objects)

## Cross-model rule

`raw_syllable_id` is model-local (ADR-0005). Downstream: pool → HDBSCAN signatures.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ensemble", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--tracking-h5", type=Path, default=DEFAULT_TRACKING)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--exclude-ct",
        type=str,
        default="0.1",
        help="Comma-separated conf_threshold values to drop (default: 0.1)",
    )
    ap.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated paramscan_* names (overrides discovery)",
    )
    ap.add_argument("--max-trials", type=int, default=None, help="Smoke-test cap per model")
    ap.add_argument("--min-bout-frames", type=int, default=3, help="Absorb threshold; 1 disables")
    ap.add_argument(
        "--append",
        action="store_true",
        help="Append to existing CSV (rewrite listed models only)",
    )
    args = ap.parse_args(argv)

    exclude_ct = {x.strip() for x in str(args.exclude_ct).split(",") if x.strip()}
    if args.models:
        models = [x.strip() for x in args.models.split(",") if x.strip()]
    else:
        models = discover_models(args.ensemble, exclude_ct=exclude_ct)

    if not models:
        print("No models to process", flush=True)
        return 1

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "syllable_bout_kinematics.csv"
    min_bout = None if int(args.min_bout_frames) <= 1 else int(args.min_bout_frames)

    manifests_all = load_manifest_csv(args.manifest_path)
    # Dedup by kpMS key; keep habituation + experimental (matches fit).
    seen: set[str] = set()
    manifests: list = []
    for m in manifests_all:
        k = kpms_recording_key(m)
        if k in seen:
            continue
        seen.add(k)
        manifests.append(m)

    if args.append:
        if not csv_path.is_file():
            raise FileNotFoundError(f"--append requires existing {csv_path}")
        existing = pd.read_csv(csv_path, keep_default_na=False)
        keep = existing[~existing["model"].isin(models)]
        keep.to_csv(csv_path, index=False)
        print(
            f"append mode: kept {len(keep):,} rows; rewriting models={models}",
            flush=True,
        )
    else:
        _write_csv_header(csv_path, KINEMATICS_FIELDS)

    alignment_cache = KpmsAlignmentCache()
    per_model: list[dict[str, object]] = []
    n_rows_total = 0
    t0 = time.time()
    last_progress = t0

    print(
        f"n_models={len(models)} n_manifests={len(manifests)} "
        f"exclude_ct={sorted(exclude_ct)} tracking={args.tracking_h5}",
        flush=True,
    )

    with h5py.File(args.tracking_h5, "r") as tracking_h5:
        for i, model in enumerate(models, start=1):
            meta = parse_model(model)
            results_path = args.ensemble / model / "results.h5"
            if not results_path.is_file():
                print(f"[{i}/{len(models)}] MISSING {results_path}", flush=True)
                per_model.append({"model": model, "status": "missing_results_h5"})
                continue

            pre_cfg = KpmsPreprocessConfig(
                min_fragment_frames=4,
                jump_filter_cm=15.0,
                jump_filter_lookahead_frames=3,
                px_per_cm=2.42,
                retain_all_frames=False,
                db_path=args.tracking_h5,
                pose_stream="anatomical",
                conf_threshold=float(meta["ct_f"]),
            )

            with h5py.File(results_path, "r") as kpms_h5:
                keys_in_model = set(kpms_h5.keys())
                model_manifests = [
                    m for m in manifests if kpms_recording_key(m) in keys_in_model
                ]
                trial_iter = model_manifests
                if args.max_trials is not None:
                    trial_iter = model_manifests[: int(args.max_trials)]

                print(
                    f"[{i}/{len(models)}] {model} trials={len(trial_iter)} "
                    f"ct={meta['ct']} ss={meta['ss']}",
                    flush=True,
                )
                status_counts: Counter[str] = Counter()
                n_rows = 0
                n_trials_ok = 0
                t_model = time.time()
                for ti, manifest in enumerate(trial_iter, start=1):
                    rows, status = build_trial_rows(
                        manifest=manifest,
                        kpms_h5=kpms_h5,
                        tracking_h5=tracking_h5,
                        alignment_cache=alignment_cache,
                        pre_cfg=pre_cfg,
                        model=model,
                        ss=int(meta["ss"]),
                        min_bout_frames=min_bout,
                        ambiguous_threshold_mps=DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
                    )
                    status_counts[status] += 1
                    if status == "ok":
                        n_trials_ok += 1
                        if rows:
                            _append_csv_rows(csv_path, KINEMATICS_FIELDS, rows)
                            n_rows += len(rows)
                    now = time.time()
                    if ti % 50 == 0 or (now - last_progress) >= 45:
                        rate = ti / max(now - t_model, 1e-6)
                        eta_s = (len(trial_iter) - ti) / max(rate, 1e-6)
                        print(
                            f"  [{model}] {ti}/{len(trial_iter)} "
                            f"ok={n_trials_ok} bouts={n_rows} "
                            f"{rate:.2f} trials/s ETA={eta_s / 60:.1f}min "
                            f"status={dict(status_counts)}",
                            flush=True,
                        )
                        last_progress = now

            summary = {
                "model": model,
                "status": "ok",
                "results_h5": str(results_path),
                "ct": meta["ct"],
                "ss": meta["ss"],
                "n_trials_attempted": len(trial_iter),
                "n_trials_ok": n_trials_ok,
                "n_bout_rows": n_rows,
                "status_counts": dict(status_counts),
            }
            per_model.append(summary)
            n_rows_total += n_rows
            print(
                f"  done {model}: trials_ok={n_trials_ok}/{len(trial_iter)} bouts={n_rows}",
                flush=True,
            )

    run_summary = {
        "ensemble": str(args.ensemble),
        "tracking_h5": str(args.tracking_h5),
        "manifest_path": str(args.manifest_path),
        "out_csv": str(csv_path),
        "exclude_ct": sorted(exclude_ct),
        "models": models,
        "append": bool(args.append),
        "min_bout_frames": min_bout,
        "condition_layer": "run",
        "n_bout_rows_written_this_run": n_rows_total,
        "elapsed_s": round(time.time() - t0, 1),
        "per_model": per_model,
    }
    (out / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    (out / "INFO_syllable_kinematics.md").write_text(
        _info_md(exclude_ct=sorted(exclude_ct), n_models=len(models)),
        encoding="utf-8",
    )
    print(
        f"Wrote {n_rows_total} bout rows -> {csv_path} ({run_summary['elapsed_s']}s)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
