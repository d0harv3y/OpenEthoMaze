"""Probe legacy / pipeline H5 schema for S1 anchor investigation.

Usage (PowerShell, from repo root):
  uv run python scratch/2026-06-30-legacy-h5-schema/probe_legacy_h5.py --h5 PATH [--manifest PATH] [--trial ANIMAL/SESSION/TRIAL]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from maze.core.schema import XY_ROW_DTYPE  # noqa: E402
from maze.pipeline.db.trial_key import TrialKey  # noqa: E402
from maze.pipeline.io.file_discovery import TrialManifest, load_manifest_csv  # noqa: E402


def _decode(v: object) -> str:
    if isinstance(v, (bytes, np.bytes_)):
        return v.decode("utf-8", errors="replace")
    return str(v)


def _summarize_trial(g: h5py.Group, path: str) -> dict:
    out: dict = {"path": path, "attrs": {k: _decode(g.attrs[k]) for k in g.attrs.keys()}}
    children = {}
    for name in g.keys():
        child = g[name]
        if isinstance(child, h5py.Dataset):
            children[name] = {
                "kind": "dataset",
                "shape": child.shape,
                "dtype": str(child.dtype),
            }
        else:
            children[name] = {"kind": "group", "keys": list(child.keys())[:20]}
    out["children"] = children

    amb = None
    for amb_name in ("ambulation_metrics", "ambulation metrics"):
        if amb_name in g:
            amb = g[amb_name]
            break
    if amb is not None:
        points = {}
        for pt in amb.keys():
            pt_g = amb[pt]
            pt_info: dict = {"keys": list(pt_g.keys())}
            if "xy" in pt_g:
                xy = pt_g["xy"]
                rec = xy[()]
                names = rec.dtype.names or ()
                pt_info["xy"] = {
                    "n_rows": int(rec.shape[0]),
                    "dtype_names": list(names),
                    "matches_XY_ROW_DTYPE": rec.dtype == XY_ROW_DTYPE,
                }
                if "frame_index" in names:
                    fi = np.asarray(rec["frame_index"], dtype=np.int64)
                    pt_info["xy"]["frame_index"] = {
                        "min": int(fi.min()) if len(fi) else None,
                        "max": int(fi.max()) if len(fi) else None,
                        "strictly_increasing": bool(np.all(np.diff(fi) > 0)) if len(fi) > 1 else True,
                        "equals_row_index": bool(np.array_equal(fi, np.arange(len(fi)))),
                    }
                if "trial_state" in names:
                    states = [_decode(s) for s in rec["trial_state"]]
                    uniq, counts = np.unique(states, return_counts=True)
                    pt_info["xy"]["trial_state_counts"] = {
                        str(u): int(c) for u, c in zip(uniq, counts, strict=True)
                    }
                if "is_moving" in names:
                    im = np.asarray(rec["is_moving"], dtype=bool)
                    pt_info["xy"]["is_moving_frac"] = float(im.mean()) if len(im) else 0.0
            points[pt] = pt_info
        out["ambulation_metrics"] = points

    if "tracking" in g:
        tr = g["tracking"]
        out["tracking"] = {name: list(tr[name].keys()) if isinstance(tr[name], h5py.Group) else "dataset" for name in tr.keys()}
    return out


def _speed_from_xy(rec: np.ndarray, fps: float, px_per_cm: float) -> np.ndarray:
    xy = np.column_stack((rec["x"].astype(np.float64), rec["y"].astype(np.float64)))
    n = len(xy)
    out = np.zeros(n, dtype=np.float64)
    if n < 2 or fps <= 0 or px_per_cm <= 0:
        return out
    step_px = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    m_per_px = 1.0 / (px_per_cm * 100.0)
    out[1:] = step_px * m_per_px * fps
    return out


def _alignment_probe(
    legacy_h5: Path,
    manifest: TrialManifest,
    *,
    kpms_results_h5: Path | None,
    seed: str = "042",
) -> dict:
    from maze.kpms.apply_summary import preprocess_config_from_apply_summary
    from maze.kpms.frame_alignment import kpms_aligned_coordinates_and_indices, kpms_recording_key
    from maze.kpms.preprocess import KpmsPreprocessConfig

    key = TrialKey.from_manifest(manifest)
    out: dict = {"trial_key": key.path(), "kpms_recording_key": kpms_recording_key(manifest)}

    with h5py.File(legacy_h5, "r") as h5:
        gpath = key.path().lstrip("/")
        if gpath not in h5:
            out["error"] = f"trial group missing: {gpath}"
            return out
        g = h5[gpath]
        fps = float(g.attrs.get("fps") or g.attrs.get("h5_fps") or 30.0)
        px_per_cm = float(g.attrs.get("px_per_cm") or 2.42)
        out["fps"] = fps
        out["px_per_cm"] = px_per_cm

        xy = None
        point_used = None
        for amb_name in ("ambulation_metrics", "ambulation metrics"):
            if amb_name not in g:
                continue
            amb = g[amb_name]
            for point in ("spot_hybrid", "center", "spot"):
                if point in amb and "xy" in amb[point]:
                    xy = amb[point]["xy"][()]
                    point_used = point
                    break
            if xy is not None:
                break
        if xy is None:
            out["error"] = "no spot_hybrid/center/spot xy table"
            return out
        out["point"] = point_used
        names = xy.dtype.names or ()
        if "frame_index" in names:
            fi = np.asarray(xy["frame_index"], dtype=np.int64)
            out["legacy_frame_index"] = {
                "len": len(fi),
                "min": int(fi.min()),
                "max": int(fi.max()),
                "row_eq_index": bool(np.array_equal(fi, np.arange(len(fi)))),
            }
        speed = _speed_from_xy(xy, fps, px_per_cm)
        out["legacy_speed_mps"] = {
            "p50": float(np.nanpercentile(speed, 50)),
            "p95": float(np.nanpercentile(speed, 95)),
            "max": float(np.nanmax(speed)),
        }

    if kpms_results_h5 is None or not kpms_results_h5.is_file():
        out["kpms_alignment"] = "skipped (no results_apply.h5)"
        return out

    pre_cfg = preprocess_config_from_apply_summary(kpms_results_h5) or KpmsPreprocessConfig()
    pre_cfg = KpmsPreprocessConfig(
        min_fragment_frames=pre_cfg.min_fragment_frames,
        jump_filter_cm=pre_cfg.jump_filter_cm,
        jump_filter_lookahead_frames=pre_cfg.jump_filter_lookahead_frames,
        px_per_cm=pre_cfg.px_per_cm or px_per_cm,
        retain_all_frames=pre_cfg.retain_all_frames,
        db_path=legacy_h5,
        pose_stream=pre_cfg.pose_stream,
    )
    aligned = kpms_aligned_coordinates_and_indices(manifest, pre_cfg)
    if aligned is None:
        out["kpms_alignment"] = "kpms_aligned_coordinates_and_indices returned None"
        return out
    _rk, _coord, src_idx = aligned
    out["kpms_alignment"] = {
        "n_kpms_rows": int(len(src_idx)),
        "src_idx_min": int(src_idx.min()),
        "src_idx_max": int(src_idx.max()),
        "src_idx_strictly_increasing": bool(np.all(np.diff(src_idx) > 0)) if len(src_idx) > 1 else True,
    }
    if "frame_index" in (xy.dtype.names or ()):
        fi = np.asarray(xy["frame_index"], dtype=np.int64)
        # Map kpMS rows to legacy speed via source_frame_index join (S0 contract pattern)
        if np.all((src_idx >= 0) & (src_idx < len(fi))):
            legacy_at_kpms = speed[src_idx]
            out["join"] = {
                "method": "speed[src_idx] where src_idx = frame_index column",
                "n_matched": int(len(src_idx)),
                "speed_p50_at_kpms_rows": float(np.nanpercentile(legacy_at_kpms, 50)),
            }
        else:
            out["join"] = {"error": "src_idx out of range for legacy xy length"}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe legacy VAST / pipeline H5 schema")
    ap.add_argument("--h5", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=None)
    ap.add_argument("--trial", type=str, default=None, help="animal_id/session/trial e.g. 3243/S01/T01")
    ap.add_argument("--kpms-root", type=Path, default=None)
    ap.add_argument("--seed", type=str, default="042")
    ap.add_argument("--max-trials", type=int, default=3)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    h5_path = args.h5.resolve()
    if not h5_path.is_file():
        print(f"Missing: {h5_path}", file=sys.stderr)
        return 1

    report: dict = {"h5": str(h5_path), "root_keys_sample": []}

    with h5py.File(h5_path, "r") as h5:
        report["root_keys_sample"] = list(h5.keys())[:15]
        report["n_root_children"] = len(h5.keys())
        trials: list[dict] = []
        if args.trial:
            parts = args.trial.strip("/").split("/")
            if len(parts) != 3:
                print("--trial must be animal/session/trial", file=sys.stderr)
                return 1
            path = "/".join(parts)
            if path in h5:
                trials.append(_summarize_trial(h5[path], path))
            else:
                report["trial_error"] = f"not found: {path}"
        else:
            count = 0
            for aid in h5.keys():
                if not isinstance(h5[aid], h5py.Group):
                    continue
                for sid in h5[aid].keys():
                    if not isinstance(h5[aid][sid], h5py.Group):
                        continue
                    for tid in h5[aid][sid].keys():
                        path = f"{aid}/{sid}/{tid}"
                        trials.append(_summarize_trial(h5[path], path))
                        count += 1
                        if count >= args.max_trials:
                            break
                    if count >= args.max_trials:
                        break
                if count >= args.max_trials:
                    break
        report["trials"] = trials

    if args.manifest and args.manifest.is_file():
        manifests = load_manifest_csv(args.manifest)
        if args.trial:
            parts = args.trial.strip("/").split("/")
            manifests = [
                m
                for m in manifests
                if str(m.animal_id) == parts[0] and m.session == parts[1] and m.trial == parts[2]
            ]
        elif manifests:
            manifests = manifests[:1]
        alignments = []
        kpms_root = args.kpms_root
        results_h5 = None
        if kpms_root is not None:
            results_h5 = kpms_root / "anatomical" / f"seed_{args.seed}" / "results_apply.h5"
        for m in manifests[: args.max_trials]:
            alignments.append(
                _alignment_probe(h5_path, m, kpms_results_h5=results_h5, seed=args.seed)
            )
        report["alignment_probes"] = alignments

    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
