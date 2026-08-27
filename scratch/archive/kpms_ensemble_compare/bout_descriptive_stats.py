#!/usr/bin/env python3
"""Descriptive statistics for syllable bouts (scratch, read-only).

Aggregates bout-level length and kinematics across seeds for clustering review.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import keypoint_moseq as kpms
import numpy as np

_SCRATCH_DIR = Path(__file__).resolve().parent
if str(_SCRATCH_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_DIR))

from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.io.file_discovery import load_manifest_csv
from movement_layer import load_ambulation_xy, movement_series_for_trial  # noqa: E402
from behavior_ethogram_phase_i import SEEDS  # noqa: E402
from syllable_speed_cluster import (  # noqa: E402
    _decode_state,
    _iter_bouts,
    _phase_mask,
)

PhaseKind = str


@dataclass
class BoutRecord:
    seed: str
    stream: str
    raw_syllable_id: int
    bout_frames: int
    mean_speed_mps: float
    mean_abs_dheading: float
    frac_still: float


def _percentiles(arr: np.ndarray, ps: tuple[int, ...] = (5, 25, 50, 75, 95)) -> dict[str, float]:
    if arr.size == 0:
        return {f"p{p}": float("nan") for p in ps}
    vals = np.percentile(arr, ps)
    return {f"p{p}": float(v) for p, v in zip(ps, vals, strict=True)}


def _summary_block(name: str, arr: np.ndarray) -> dict[str, object]:
    return {
        "name": name,
        "n": int(arr.size),
        "mean": float(np.mean(arr)) if arr.size else float("nan"),
        "std": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
        **_percentiles(arr),
        "min": float(np.min(arr)) if arr.size else float("nan"),
        "max": float(np.max(arr)) if arr.size else float("nan"),
    }


def collect_bout_records(
    *,
    kpms_root: Path,
    legacy_db: Path,
    manifest_path: Path,
    stream: str,
    seeds: tuple[str, ...],
    phase: PhaseKind,
    min_bout_frames: int,
    tracking_h5: Path | None,
) -> list[BoutRecord]:
    manifests = {m.kpms_results_dict_key: m for m in load_manifest_csv(manifest_path)}
    track_db = tracking_h5 or (kpms_root / "kpms_tracking.h5")
    records: list[BoutRecord] = []

    for seed in seeds:
        results_path = kpms_root / stream / f"seed_{seed}" / "results_apply.h5"
        if not results_path.is_file():
            continue
        pre_cfg = KpmsPreprocessConfig(
            min_fragment_frames=4,
            jump_filter_cm=15.0,
            jump_filter_lookahead_frames=3,
            px_per_cm=2.42,
            retain_all_frames=False,
            db_path=track_db,
            pose_stream=stream,  # type: ignore[arg-type]
        )
        results = kpms.load_hdf5(str(results_path))
        for _tkey, rec in results.items():
            manifest = manifests.get(_tkey)
            if manifest is None:
                continue
            syll = np.asarray(rec["syllable"]).ravel()
            heading = np.asarray(rec.get("heading", np.zeros_like(syll))).ravel()
            mv = movement_series_for_trial(
                manifest,
                stream,  # type: ignore[arg-type]
                legacy_db,
                pre_cfg=pre_cfg,
            )
            if mv is None or mv.source_frames.shape[0] != syll.shape[0]:
                continue
            xy = load_ambulation_xy(legacy_db, manifest)
            if xy is None:
                continue
            fts = {int(row["frame_index"]): _decode_state(row["trial_state"]) for row in xy}
            states = np.array([fts.get(int(f), "") for f in mv.source_frames], dtype=object)
            mask = _phase_mask(states, phase)  # type: ignore[arg-type]

            for sid, sl in _iter_bouts(syll, mask, min_bout_frames=min_bout_frames):
                spd = mv.speed_mps[sl]
                hd = heading[sl]
                still = mv.is_moving[sl]
                if hd.size >= 2:
                    dh = float(np.mean(np.abs(np.diff(np.unwrap(hd.astype(np.float64))))))
                else:
                    dh = 0.0
                records.append(
                    BoutRecord(
                        seed=seed,
                        stream=stream,
                        raw_syllable_id=int(sid),
                        bout_frames=int(sl.stop - sl.start),
                        mean_speed_mps=float(np.mean(spd)),
                        mean_abs_dheading=dh,
                        frac_still=float(np.mean(~still.astype(bool))),
                    )
                )
    return records


def summarize_bouts(records: list[BoutRecord]) -> dict[str, object]:
    if not records:
        return {"n_bouts": 0}
    frames = np.array([r.bout_frames for r in records], dtype=np.float64)
    speed = np.array([r.mean_speed_mps for r in records], dtype=np.float64)
    dheading = np.array([r.mean_abs_dheading for r in records], dtype=np.float64)
    still = np.array([r.frac_still for r in records], dtype=np.float64)

    by_proto: dict[tuple[str, int], list[BoutRecord]] = defaultdict(list)
    for r in records:
        by_proto[(r.seed, r.raw_syllable_id)].append(r)

    proto_n_bouts = np.array([len(v) for v in by_proto.values()], dtype=np.float64)
    proto_speed_iqr = []
    for bout_list in by_proto.values():
        if len(bout_list) < 2:
            continue
        means = np.array([b.mean_speed_mps for b in bout_list], dtype=np.float64)
        q75, q25 = np.percentile(means, [75, 25])
        proto_speed_iqr.append(float(q75 - q25))

    derived_t_s = []
    for bout_list in by_proto.values():
        lengths = [b.bout_frames for b in bout_list]
        med = float(np.median(lengths))
        derived_t_s.append(float(np.clip(round(1.5 * med), 8, 30)))

    return {
        "n_bouts": len(records),
        "n_prototypes": len(by_proto),
        "n_seeds": len({r.seed for r in records}),
        "bout_frames": _summary_block("bout_frames", frames),
        "bout_mean_speed_mps": _summary_block("bout_mean_speed_mps", speed),
        "bout_mean_abs_dheading": _summary_block("bout_mean_abs_dheading", dheading),
        "bout_frac_still": _summary_block("bout_frac_still", still),
        "prototypes_per_seed": _summary_block(
            "prototypes_with_bouts",
            np.array([sum(1 for k in by_proto if k[0] == s) for s in sorted({r.seed for r in records})]),
        ),
        "bouts_per_prototype": _summary_block("bouts_per_prototype", proto_n_bouts),
        "prototype_bout_speed_iqr": _summary_block(
            "prototype_bout_speed_iqr",
            np.asarray(proto_speed_iqr, dtype=np.float64),
        ),
        "derived_T_s": _summary_block("derived_T_s", np.asarray(derived_t_s, dtype=np.float64)),
        "padding_dims_at_Tmax30": _summary_block(
            "n_pad_dims_if_Tmax_30",
            3 * (30 - np.asarray(derived_t_s, dtype=np.float64)),
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kpms-root", type=Path, required=True)
    parser.add_argument("--legacy-db", type=Path, required=True)
    parser.add_argument("--manifest-path", type=Path, required=True)
    parser.add_argument("--stream", default="anatomical")
    parser.add_argument("--seeds", nargs="*", default=None)
    parser.add_argument("--phase", choices=("all", "run", "iti"), default="all")
    parser.add_argument("--min-bout-frames", type=int, default=4)
    parser.add_argument("--tracking-h5", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-csv", type=Path, default=None)
    args = parser.parse_args()

    seeds = tuple(args.seeds) if args.seeds else SEEDS
    records = collect_bout_records(
        kpms_root=args.kpms_root.expanduser().resolve(),
        legacy_db=args.legacy_db.expanduser().resolve(),
        manifest_path=args.manifest_path.expanduser().resolve(),
        stream=args.stream,
        seeds=seeds,
        phase=args.phase,
        min_bout_frames=args.min_bout_frames,
        tracking_h5=args.tracking_h5.expanduser().resolve() if args.tracking_h5 else None,
    )
    summary = summarize_bouts(records)
    summary["stream"] = args.stream
    summary["phase"] = args.phase
    summary["seeds"] = list(seeds)
    text = json.dumps(summary, indent=2)
    print(text)

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(text, encoding="utf-8")
    if args.out_csv:
        args.out_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.out_csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(asdict(records[0]).keys()) if records else [])
            if records:
                w.writeheader()
                for r in records:
                    w.writerow(asdict(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
