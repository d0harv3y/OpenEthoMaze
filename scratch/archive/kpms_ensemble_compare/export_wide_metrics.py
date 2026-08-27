#!/usr/bin/env python3
"""Export kpMS ensemble syllable + speed traces as one bizarre wide CSV.

Each row is one (trial, stream, seed, metric) combination. Frame values are on the
kpMS preprocess-kept timeline (same length as ``results_apply.h5`` syllable vector).
Speed is legacy ambulation (spot/centroid) sampled at the aligned source frames.

Column layout::

    stream, seed, id, tx, strain, sex, session#, trial#, exit#, metric,
    frame_1, frame_2, ... frame_N

Rows ≈ n_trials × 2 metrics × 14 models (excludes incomplete ``fused/seed_005``).

Example::

    uv run python scratch/kpms_ensemble_compare/export_wide_metrics.py \\
        --root "C:/Users/admin/Documents/work/sack/test" \\
        --out scratch/kpms_ensemble_compare/output/ensemble_wide_metrics.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import keypoint_moseq as kpms
import numpy as np

from maze.pipeline.io.file_discovery import TrialManifest, load_manifest_csv

_SCRATCH_DIR = Path(__file__).resolve().parent
if str(_SCRATCH_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_DIR))

from movement_layer import movement_series_for_trial  # noqa: E402

DEFAULT_LEGACY_DB = Path(r"C:\Users\admin\Documents\work\sack\test\vast_results_legacy.h5")

STREAMS = ("anatomical", "blob", "fused")
SEEDS = ("005", "013", "042", "067", "111")
METRICS = ("syllable#", "speed")


@dataclass(frozen=True)
class ModelRef:
    stream: str
    seed: str

    @property
    def model_id(self) -> str:
        return f"{self.stream}/seed_{self.seed}"


def model_results_path(root: Path, model: ModelRef) -> Path:
    return root / model.stream / f"seed_{model.seed}" / "results_apply.h5"


def discover_models(root: Path) -> list[ModelRef]:
    models: list[ModelRef] = []
    for stream in STREAMS:
        for seed in SEEDS:
            model = ModelRef(stream=stream, seed=seed)
            path = model_results_path(root, model)
            if not path.is_file():
                raise FileNotFoundError(path)
            models.append(model)
    return models


_SESSION_NUM = re.compile(r"^[hH]?[sS]?0*(\d+)$")


def session_number(session: str) -> str:
    """``S01`` -> ``1``; ``hS03`` -> ``3``."""
    m = _SESSION_NUM.match(str(session).strip())
    return m.group(1) if m else str(session)


def trial_number(trial: str) -> str:
    t = str(trial).strip()
    if len(t) >= 2 and t[0].upper() == "T" and t[1:].isdigit():
        return str(int(t[1:]))
    if t.isdigit():
        return str(int(t))
    return t


def manifest_row_meta(m: TrialManifest) -> dict[str, str]:
    exit_val = ""
    if m.exit_number is not None:
        exit_val = str(int(m.exit_number))
    return {
        "id": str(m.animal_id),
        "tx": str(m.tx or ""),
        "strain": str(m.strain or ""),
        "sex": str(m.sex or ""),
        "session#": session_number(m.session),
        "trial#": trial_number(m.trial),
        "exit#": exit_val,
    }


def pad_values(values: np.ndarray, n_cols: int) -> list[str]:
    out = [""] * n_cols
    n = min(int(values.size), n_cols)
    for i in range(n):
        v = float(values[i])
        out[i] = "" if not np.isfinite(v) else f"{v:.6g}"
    return out


def format_syllable_values(syll: np.ndarray, n_cols: int) -> list[str]:
    out = [""] * n_cols
    n = min(int(syll.size), n_cols)
    for i in range(n):
        v = int(syll[i])
        out[i] = str(v)
    return out


def scan_max_frames(root: Path, models: list[ModelRef], manifests: list[TrialManifest]) -> int:
    keys = {m.kpms_results_dict_key for m in manifests}
    max_len = 0
    for model in models:
        results = kpms.load_hdf5(str(model_results_path(root, model)))
        for key in keys:
            rec = results.get(key)
            if rec is None:
                continue
            max_len = max(max_len, int(np.asarray(rec["syllable"]).size))
    return max_len


def build_movement_cache(
    manifests: list[TrialManifest],
    legacy_db: Path,
) -> dict[tuple[str, str], np.ndarray | None]:
    """(trial_key, stream) -> speed_mps aligned to kpMS rows, or None."""
    cache: dict[tuple[str, str], np.ndarray | None] = {}
    for stream in STREAMS:
        for m in manifests:
            key = m.kpms_results_dict_key
            ck = (key, stream)
            if ck in cache:
                continue
            mv = movement_series_for_trial(m, stream, legacy_db)
            cache[ck] = None if mv is None else np.asarray(mv.speed_mps, dtype=np.float64)
    return cache


def write_wide_csv(
    *,
    root: Path,
    out_path: Path,
    legacy_db: Path,
    manifest_path: Path,
    max_frames: int | None,
) -> dict[str, int]:
    manifests = load_manifest_csv(manifest_path)
    manifests = sorted(manifests, key=lambda m: (m.animal_id, m.session, m.trial))
    models = discover_models(root)

    if max_frames is None:
        print("Scanning max frame length across models ...")
        max_frames = scan_max_frames(root, models, manifests)
    print(f"Wide frame columns: frame_1 .. frame_{max_frames} ({max_frames} cols)")

    print("Building speed cache (legacy ambulation join) ...")
    speed_cache = build_movement_cache(manifests, legacy_db)

    frame_cols = [f"frame_{i}" for i in range(1, max_frames + 1)]
    header = [
        "stream",
        "seed",
        "id",
        "tx",
        "strain",
        "sex",
        "session#",
        "trial#",
        "exit#",
        "metric",
        *frame_cols,
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_rows = 0
    n_skip = 0

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for mi, model in enumerate(models, start=1):
            print(f"[{mi}/{len(models)}] {model.model_id} ...")
            results = kpms.load_hdf5(str(model_results_path(root, model)))

            for m in manifests:
                trial_key = m.kpms_results_dict_key
                rec = results.get(trial_key)
                if rec is None:
                    n_skip += 2
                    continue

                syll = np.asarray(rec["syllable"], dtype=np.int64)
                speed = speed_cache.get((trial_key, model.stream))
                if speed is None or speed.shape[0] != syll.shape[0]:
                    n_skip += 2
                    continue

                meta = manifest_row_meta(m)
                base = [
                    model.stream,
                    model.seed,
                    meta["id"],
                    meta["tx"],
                    meta["strain"],
                    meta["sex"],
                    meta["session#"],
                    meta["trial#"],
                    meta["exit#"],
                ]

                writer.writerow([*base, METRICS[0], *format_syllable_values(syll, max_frames)])
                writer.writerow([*base, METRICS[1], *pad_values(speed, max_frames)])
                n_rows += 2

    return {
        "n_rows": n_rows,
        "n_skip": n_skip,
        "max_frames": max_frames,
        "n_models": len(models),
        "n_trials": len(manifests),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--root",
        type=Path,
        default=Path(r"C:\Users\admin\Documents\work\sack\test"),
        help="kpMS ensemble project root",
    )
    p.add_argument(
        "--legacy-db",
        type=Path,
        default=DEFAULT_LEGACY_DB,
        help="Legacy results H5 with ambulation_metrics",
    )
    p.add_argument(
        "--manifest-csv",
        type=Path,
        default=None,
        help="Trial manifest (default: <root>/trial_manifest_kpms_tracking_wsl.csv)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=_SCRATCH_DIR / "output" / "ensemble_wide_metrics.csv",
        help="Output wide CSV path",
    )
    p.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Pad/truncate to this many frame columns (default: scan max)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    manifest = args.manifest_csv or (args.root / "trial_manifest_kpms_tracking_wsl.csv")
    stats = write_wide_csv(
        root=args.root,
        out_path=args.out,
        legacy_db=args.legacy_db,
        manifest_path=manifest,
        max_frames=args.max_frames,
    )
    expected = stats["n_trials"] * 2 * stats["n_models"]
    print(f"Wrote {args.out}")
    print(
        f"Rows: {stats['n_rows']} (expected up to {expected}), "
        f"skipped {stats['n_skip']}, frame_cols={stats['max_frames']}"
    )


if __name__ == "__main__":
    main()
