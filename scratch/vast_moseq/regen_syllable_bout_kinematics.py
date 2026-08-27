"""Regen VAST syllable-bout kinematics with NOR column schema.

Cohort: keys in ``gerstner_vast_fit/results.h5`` only (drop habituation).
Alphabets (default):
  - five ``test2/anatomical/seed_*/results_apply.h5`` (filtered to primary keys)
  - ``gerstner_vast_fit/results.h5`` as a 6th alphabet (same keys; fit-on-full)

Pass 1: keep bouts whose majority ``trial_state`` is ``run`` (stimulus-on).

Spot = mean(nose, neck, spine) — matches NOR ``SPOT_NODES``.
Heading = kpMS results ``heading``.
Nose–tail from anatomical nose/tail on aligned coordinates.

Regen:
  uv run python scratch/vast_moseq/regen_syllable_bout_kinematics.py
  uv run python scratch/vast_moseq/regen_syllable_bout_kinematics.py --models gerstner_vast_fit --append
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Sequence

import h5py
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
_REPO = _SCRATCH.parent
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from maze.core.anatomy import STANDARD_NODE_NAMES  # noqa: E402
from maze.core.h5_layout import read_feedback_table  # noqa: E402
from maze.kpms.behavior_ethogram.bout_kinematics import (  # noqa: E402
    abs_dheading_per_frame,
    trial_state_for_rows,
)
from maze.kpms.behavior_ethogram.bout_scalars import (  # noqa: E402
    DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
    bout_ambiguous,
    bout_iqr,
    bout_net_dheading_rad,
    bout_straightness,
    circular_mean_sin_cos,
    syllable_runs,
)
from maze.kpms.frame_alignment import KpmsAlignmentCache, kpms_recording_key  # noqa: E402
from maze.kpms.preprocess import KpmsPreprocessConfig  # noqa: E402
from maze.pipeline.db.feedback_align import (  # noqa: E402
    align_feedback_to_xy_table,
    feedback_table_matches_xy,
    read_primary_xy_table,
)
from maze.pipeline.db.trial_key import TrialKey  # noqa: E402
from maze.pipeline.io.file_discovery import TrialManifest, load_manifest_csv  # noqa: E402
from nor_object_mi.syllable_cleanup import maybe_absorb_short_bouts  # noqa: E402

DEFAULT_PRIMARY = Path(r"C:\Users\admin\Documents\work\sack\gerstner_vast_fit\results.h5")
DEFAULT_SEED_ROOT = Path(r"C:\Users\admin\Documents\work\sack\test2\anatomical")
DEFAULT_MANIFEST = Path(r"C:\Users\admin\Documents\work\sack\test2\gerstner_manifest_local_legacy.csv")
DEFAULT_TRACKING = Path(r"C:\Users\admin\Documents\work\sack\vast_results_legacy.h5")
DEFAULT_OUT = Path(r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq\syllable_bout_kinematics")

SEEDS: tuple[str, ...] = ("005", "013", "042", "067", "111")
GERSTNER_MODEL = "gerstner_vast_fit"
DEFAULT_MODELS: tuple[str, ...] = tuple(f"seed_{s}" for s in SEEDS) + (GERSTNER_MODEL,)
KEY_RE = re.compile(r"^(?P<animal>\d+)-(?P<hab>h)?S(?P<session>\d+)-T(?P<trial>\d+)$")
SPOT_IDX = tuple(STANDARD_NODE_NAMES.index(n) for n in ("nose", "neck", "spine"))
NOSE_IDX = STANDARD_NODE_NAMES.index("nose")
TAIL_IDX = STANDARD_NODE_NAMES.index("tail")

# NOR ``KINEMATICS_FIELDS`` order (object-distance cols left NaN for VAST).
KINEMATICS_FIELDS: tuple[str, ...] = (
    "model",
    "ss",
    "kpms_key",
    "animal_id",
    "raw_session",
    "phase_layer",
    "condition_layer",
    "tx",
    "sex",
    "strain",
    "cohort",
    "bout_index",
    "raw_syllable_id",
    "row_start",
    "row_end_exclusive",
    "bout_frames",
    "fps",
    "bout_duration_s",
    "bout_mean_speed_mps",
    "bout_iqr_speed_mps",
    "bout_path_length_m",
    "bout_straightness",
    "bout_mean_abs_dheading",
    "bout_iqr_abs_dheading",
    "bout_net_dheading_rad",
    "bout_mean_heading_sin",
    "bout_mean_heading_cos",
    "ambiguous",
    "bout_valid_frame_frac",
    "bout_mean_nose_tail_m",
    "bout_iqr_nose_tail_m",
    "bout_mean_dist_any_m",
    "bout_mean_dist_fam_m",
    "bout_mean_dist_nvl_m",
    "bout_mean_dist_obj_a_m",
    "bout_mean_dist_obj_b_m",
)


def _info_md() -> str:
    return """# INFO — VAST syllable bout kinematics (NOR schema)

Grain: one row = one kpMS syllable bout × model, **run-phase only** (pass 1).

## Cohort

| Source | Role |
|--------|------|
| `gerstner_vast_fit/results.h5` | Primary key inventory (experimental only; habituation dropped) |
| `test2/anatomical/seed_*/results_apply.h5` | Five seed alphabets (syllable + heading) |
| `gerstner_vast_fit/results.h5` | 6th alphabet (fit-on-full; same primary keys) |
| `vast_results_legacy.h5` | Anatomical pose for spot / nose–tail; feedback `trial_state` |

Junk animals present only in seed apply H5 are excluded by the primary key intersect.

## Spot / heading

- **Spot** = mean(nose, neck, spine) — same nodes as NOR.
- **Heading** = kpMS apply `heading`.
- **Nose–tail** = Euclidean nose→tail length (m).
- NOR object-distance columns are present but **NaN** (no fam/nvl objects).

## Pass 1 filter

Keep bouts whose majority aligned `trial_state` is `run` (stimulus-on).
ITI (`iti_wait`) and whole-trial deferred.

## Cross-model rule

`raw_syllable_id` is model-local (ADR-0005). Use kinematic signatures / HDBSCAN for pause hunting.

## Steps (downstream DA)

Windows: `early_t1-3`, `mid_t4-6`, `late_t7-9`.
Δp steps: `mid_early`, `late_mid`, `late_early`.
`phase_layer` = session (`S01`…`S05`), treated like NOR phase.
"""


def load_primary_exp_keys(primary_h5: Path) -> set[str]:
    keys: set[str] = set()
    with h5py.File(primary_h5, "r") as f:
        for k in f.keys():
            if not isinstance(f[k], h5py.Group):
                continue
            m = KEY_RE.match(str(k))
            if m and not m.group("hab"):
                keys.add(str(k))
    return keys


def parse_key(kpms_key: str) -> dict[str, str | int]:
    m = KEY_RE.match(kpms_key)
    if not m:
        raise ValueError(f"unparseable kpms key: {kpms_key}")
    session = f"S{int(m.group('session')):02d}"
    return {
        "animal_id": m.group("animal"),
        "raw_session": session,
        "phase_layer": session,
        "trial": int(m.group("trial")),
    }


def _bout_mean(arr: np.ndarray, start: int, end: int) -> float:
    sl = arr[start:end]
    finite = sl[np.isfinite(sl)]
    if finite.size == 0:
        return float("nan")
    return float(np.mean(finite))


def _bout_sum(arr: np.ndarray, start: int, end: int) -> float:
    sl = arr[start:end]
    finite = sl[np.isfinite(sl)]
    if finite.size == 0:
        return float("nan")
    return float(np.sum(finite))


def _normalize_state(raw: str) -> str:
    s = str(raw).strip().lower()
    if s in {"run", "iti_wait", "iti"}:
        return "run" if s == "run" else "iti_wait"
    return s


def _majority_state(states: Sequence[str]) -> str:
    if not states:
        return ""
    norm = [_normalize_state(s) for s in states if str(s).strip()]
    if not norm:
        return ""
    return Counter(norm).most_common(1)[0][0]


def _aligned_feedback_states(g_trial: h5py.Group) -> np.ndarray | None:
    xy = read_primary_xy_table(g_trial)
    fb = read_feedback_table(g_trial)
    if xy is None or fb is None or len(fb) == 0:
        return None
    if "trial_state" not in fb.dtype.names:
        return None
    if feedback_table_matches_xy(fb, xy):
        table = fb
    else:
        run_start = int(g_trial.attrs.get("trial_start_frame", 0) or 0)
        table = align_feedback_to_xy_table(xy, fb, run_start_frame=run_start)
    if table is None or len(table) != len(xy):
        return None
    return np.asarray(table["trial_state"])


def _trial_fps(g_trial: h5py.Group, default: float = 30.0) -> float:
    for key in ("fps", "h5_fps", "video_fps"):
        raw = g_trial.attrs.get(key)
        if raw is None:
            continue
        fps = float(np.asarray(raw).item())
        if np.isfinite(fps) and fps > 0:
            return fps
    return float(default)


def _trial_px_per_cm(g_trial: h5py.Group, default: float) -> float:
    raw = g_trial.attrs.get("px_per_cm")
    if raw is None:
        return float(default)
    val = float(np.asarray(raw).item())
    return val if np.isfinite(val) and val > 0 else float(default)


def _spot_and_nose_tail_m(
    coordinates: np.ndarray,
    *,
    px_per_cm: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return x_m, y_m, valid, nose_tail_m on kpMS rows."""
    coord = np.asarray(coordinates, dtype=np.float64)
    if coord.ndim != 3 or coord.shape[1] < max(SPOT_IDX) + 1:
        raise ValueError(f"bad coordinates shape {coord.shape}")
    ppm = float(px_per_cm) * 100.0
    if ppm <= 0:
        raise ValueError("px_per_cm must be > 0")

    nodes = coord[:, list(SPOT_IDX), :]
    finite = np.isfinite(nodes).all(axis=2)
    valid = np.any(finite, axis=1)
    w = finite.astype(np.float64)
    w_sum = w.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        x_px = np.where(valid, (nodes[:, :, 0] * w).sum(axis=1) / w_sum, np.nan)
        y_px = np.where(valid, (nodes[:, :, 1] * w).sum(axis=1) / w_sum, np.nan)

    nose = coord[:, NOSE_IDX, :]
    tail = coord[:, TAIL_IDX, :]
    nt_ok = np.isfinite(nose).all(axis=1) & np.isfinite(tail).all(axis=1)
    nose_tail = np.full(coord.shape[0], np.nan, dtype=np.float64)
    nose_tail[nt_ok] = np.hypot(nose[nt_ok, 0] - tail[nt_ok, 0], nose[nt_ok, 1] - tail[nt_ok, 1]) / ppm

    x_m = x_px / ppm
    y_m = y_px / ppm
    return x_m, y_m, valid, nose_tail


def _speed_and_step_m(
    x_m: np.ndarray,
    y_m: np.ndarray,
    valid: np.ndarray,
    fps: float,
) -> tuple[np.ndarray, np.ndarray]:
    n = int(x_m.shape[0])
    speed = np.full(n, np.nan, dtype=np.float64)
    step = np.full(n, np.nan, dtype=np.float64)
    if n < 2 or not np.isfinite(fps) or fps <= 0:
        return speed, step
    d = np.hypot(np.diff(x_m), np.diff(y_m))
    ok = valid[:-1] & valid[1:] & np.isfinite(d)
    step_vals = np.full(n - 1, np.nan, dtype=np.float64)
    speed_vals = np.full(n - 1, np.nan, dtype=np.float64)
    step_vals[ok] = d[ok]
    speed_vals[ok] = d[ok] * float(fps)
    step[1:] = step_vals
    speed[1:] = speed_vals
    return speed, step


def _resolve_trial_group(tracking_h5: h5py.File, manifest: TrialManifest) -> h5py.Group | None:
    key = TrialKey.from_manifest(manifest)
    path = key.path().lstrip("/")
    if path in tracking_h5:
        return tracking_h5[path]
    # Fall back: animal/session/trial nesting already covered by TrialKey.path.
    return None


def build_trial_rows(
    *,
    manifest: TrialManifest,
    kpms_h5: h5py.File,
    tracking_h5: h5py.File,
    alignment_cache: KpmsAlignmentCache,
    pre_cfg: KpmsPreprocessConfig,
    model: str,
    ss: int,
    min_bout_frames: int | None,
    ambiguous_threshold_mps: float,
) -> tuple[list[dict[str, object]], str]:
    recording_key = kpms_recording_key(manifest)
    if recording_key not in kpms_h5:
        return [], "missing_kpms_key"
    rec = kpms_h5[recording_key]
    if "syllable" not in rec or "heading" not in rec:
        return [], "missing_syllable_or_heading"

    aligned = alignment_cache.aligned_trial(manifest, pre_cfg)
    if aligned is None:
        return [], "alignment_failed"
    coordinates = aligned.coordinates
    src_idx = aligned.source_frame_indices

    syll = maybe_absorb_short_bouts(rec["syllable"][()], min_bout_frames)
    heading = np.asarray(rec["heading"][()], dtype=np.float64).ravel()
    n = min(len(syll), len(heading), len(coordinates), len(src_idx))
    if n <= 0:
        return [], "empty_aligned"
    syll = syll[:n]
    heading = heading[:n]
    coordinates = coordinates[:n]
    src_idx = np.asarray(src_idx[:n], dtype=np.int64)

    g_trial = _resolve_trial_group(tracking_h5, manifest)
    if g_trial is None:
        return [], "missing_tracking_trial"
    fps = _trial_fps(g_trial)
    px_per_cm = _trial_px_per_cm(g_trial, float(pre_cfg.px_per_cm or 2.42))

    fb_states = _aligned_feedback_states(g_trial)
    if fb_states is None:
        return [], "missing_trial_state"
    row_states = trial_state_for_rows(fb_states, src_idx)

    x_m, y_m, valid, nose_tail = _spot_and_nose_tail_m(coordinates, px_per_cm=px_per_cm)
    speed, step_m = _speed_and_step_m(x_m, y_m, valid, fps)
    abs_dh = abs_dheading_per_frame(heading)
    xy = np.column_stack([x_m, y_m])

    key_meta = parse_key(recording_key)
    rows: list[dict[str, object]] = []
    for bout_index, (sid, start, end) in enumerate(syllable_runs(syll)):
        primary = _majority_state(row_states[start:end])
        if primary != "run":
            continue
        speed_sl = speed[start:end]
        dh_sl = abs_dh[start:end]
        nt_sl = nose_tail[start:end]
        h_sl = heading[start:end]
        valid_sl = valid[start:end]
        n_frames = int(end - start)
        speed_iqr = bout_iqr(speed_sl)
        mean_sin, mean_cos = circular_mean_sin_cos(h_sl)
        finite_speed = speed_sl[np.isfinite(speed_sl)]
        mean_speed = float(np.mean(finite_speed)) if finite_speed.size else float("nan")
        finite_dh = dh_sl[np.isfinite(dh_sl)]
        mean_dh = float(np.mean(finite_dh)) if finite_dh.size else float("nan")
        rows.append(
            {
                "model": model,
                "ss": ss,
                "kpms_key": recording_key,
                "animal_id": str(manifest.animal_id),
                "raw_session": key_meta["raw_session"],
                "phase_layer": key_meta["phase_layer"],
                "condition_layer": "run",
                "tx": str(getattr(manifest, "tx", "") or "n/a"),
                "sex": str(getattr(manifest, "sex", "") or ""),
                "strain": str(getattr(manifest, "strain", "") or "").lower(),
                "cohort": str(getattr(manifest, "cohort", "") or ""),
                "bout_index": int(bout_index),
                "raw_syllable_id": int(sid),
                "row_start": int(start),
                "row_end_exclusive": int(end),
                "bout_frames": n_frames,
                "fps": float(fps),
                "bout_duration_s": float(n_frames) / float(fps) if fps > 0 else float("nan"),
                "bout_mean_speed_mps": mean_speed,
                "bout_iqr_speed_mps": speed_iqr,
                "bout_path_length_m": _bout_sum(step_m, start, end),
                "bout_straightness": bout_straightness(xy[start:end]),
                "bout_mean_abs_dheading": mean_dh,
                "bout_iqr_abs_dheading": bout_iqr(dh_sl),
                "bout_net_dheading_rad": bout_net_dheading_rad(h_sl),
                "bout_mean_heading_sin": mean_sin,
                "bout_mean_heading_cos": mean_cos,
                "ambiguous": int(bout_ambiguous(speed_iqr, threshold_mps=ambiguous_threshold_mps)),
                "bout_valid_frame_frac": (
                    float(np.mean(valid_sl.astype(np.float64))) if n_frames else float("nan")
                ),
                "bout_mean_nose_tail_m": _bout_mean(nose_tail, start, end),
                "bout_iqr_nose_tail_m": bout_iqr(nt_sl),
                "bout_mean_dist_any_m": float("nan"),
                "bout_mean_dist_fam_m": float("nan"),
                "bout_mean_dist_nvl_m": float("nan"),
                "bout_mean_dist_obj_a_m": float("nan"),
                "bout_mean_dist_obj_b_m": float("nan"),
            }
        )
    return rows, "ok"


def _write_csv_header(path: Path, fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=list(fieldnames)).writeheader()


def _append_csv_rows(path: Path, fieldnames: Sequence[str], rows: Sequence[dict[str, object]]) -> None:
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def resolve_model_results(
    model: str,
    *,
    seed_root: Path,
    primary_h5: Path,
) -> Path:
    """Map alphabet name to kpMS results H5."""
    if model == GERSTNER_MODEL:
        return primary_h5
    if model.startswith("seed_"):
        return seed_root / model / "results_apply.h5"
    if model.isdigit() or (len(model) == 3 and model.isalnum()):
        return seed_root / f"seed_{model}" / "results_apply.h5"
    raise ValueError(f"unknown model {model!r}")


def normalize_model_name(model: str) -> str:
    if model == GERSTNER_MODEL:
        return GERSTNER_MODEL
    if model.startswith("seed_"):
        return model
    return f"seed_{model}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--primary-h5", type=Path, default=DEFAULT_PRIMARY)
    ap.add_argument("--seed-root", type=Path, default=DEFAULT_SEED_ROOT)
    ap.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--tracking-h5", type=Path, default=DEFAULT_TRACKING)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated alphabets (default: five seeds + gerstner_vast_fit)",
    )
    ap.add_argument("--seed", type=str, default=None, help="Legacy: single seed id, e.g. 042")
    ap.add_argument(
        "--append",
        action="store_true",
        help="Append to existing CSV (rewrite listed models only)",
    )
    ap.add_argument("--max-trials", type=int, default=None, help="Smoke-test cap per model")
    ap.add_argument("--min-bout-frames", type=int, default=3, help="Absorb threshold; 1 disables")
    ap.add_argument("--ss", type=int, default=100)
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "syllable_bout_kinematics.csv"

    primary_keys = load_primary_exp_keys(args.primary_h5)
    manifests_all = load_manifest_csv(args.manifest_path)
    manifests = [
        m
        for m in manifests_all
        if (not bool(getattr(m, "is_habituation", False)))
        and kpms_recording_key(m) in primary_keys
    ]
    seen: set[str] = set()
    deduped: list[TrialManifest] = []
    for m in manifests:
        k = kpms_recording_key(m)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(m)
    manifests = deduped

    if args.models:
        models = tuple(normalize_model_name(x.strip()) for x in args.models.split(",") if x.strip())
    elif args.seed:
        models = (normalize_model_name(args.seed),)
    else:
        models = DEFAULT_MODELS
    min_bout = None if int(args.min_bout_frames) <= 1 else int(args.min_bout_frames)

    if args.append:
        if not csv_path.is_file():
            raise FileNotFoundError(f"--append requires existing {csv_path}")
        existing = pd.read_csv(csv_path, keep_default_na=False)
        keep = existing[~existing["model"].isin(models)]
        keep.to_csv(csv_path, index=False)
        print(
            f"append mode: kept {len(keep):,} rows; rewriting models={list(models)}",
            flush=True,
        )
    else:
        _write_csv_header(csv_path, KINEMATICS_FIELDS)

    alignment_cache = KpmsAlignmentCache()
    pre_cfg = KpmsPreprocessConfig(
        min_fragment_frames=4,
        jump_filter_cm=15.0,
        jump_filter_lookahead_frames=3,
        px_per_cm=2.42,
        retain_all_frames=False,
        db_path=args.tracking_h5,
        pose_stream="anatomical",
    )

    per_model: list[dict[str, object]] = []
    n_rows_total = 0
    t0 = time.time()

    with h5py.File(args.tracking_h5, "r") as tracking_h5:
        for i, model in enumerate(models, start=1):
            results_path = resolve_model_results(
                model, seed_root=args.seed_root, primary_h5=args.primary_h5
            )
            if not results_path.is_file():
                print(f"[{i}/{len(models)}] MISSING {results_path}", flush=True)
                per_model.append({"model": model, "status": "missing_results_h5"})
                continue
            print(
                f"[{i}/{len(models)}] {model} trials={len(manifests)} <- {results_path.name}",
                flush=True,
            )
            status_counts: Counter[str] = Counter()
            n_rows = 0
            n_trials_ok = 0
            trial_iter = manifests
            if args.max_trials is not None:
                trial_iter = manifests[: int(args.max_trials)]
            t_seed = time.time()
            with h5py.File(results_path, "r") as kpms_h5:
                for ti, manifest in enumerate(trial_iter, start=1):
                    rows, status = build_trial_rows(
                        manifest=manifest,
                        kpms_h5=kpms_h5,
                        tracking_h5=tracking_h5,
                        alignment_cache=alignment_cache,
                        pre_cfg=pre_cfg,
                        model=model,
                        ss=int(args.ss),
                        min_bout_frames=min_bout,
                        ambiguous_threshold_mps=DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
                    )
                    status_counts[status] += 1
                    if status == "ok":
                        n_trials_ok += 1
                        if rows:
                            _append_csv_rows(csv_path, KINEMATICS_FIELDS, rows)
                            n_rows += len(rows)
                    if ti % 50 == 0 or (time.time() - t_seed) > 45:
                        rate = ti / max(time.time() - t_seed, 1e-6)
                        print(
                            f"  [{model}] {ti}/{len(trial_iter)} "
                            f"ok={n_trials_ok} bouts={n_rows} "
                            f"{rate:.2f} trials/s status={dict(status_counts)}",
                            flush=True,
                        )
                        t_seed = time.time()
            summary = {
                "model": model,
                "status": "ok",
                "results_h5": str(results_path),
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

    n_csv = n_rows_total
    if args.append and csv_path.is_file():
        with csv_path.open("r", encoding="utf-8") as f:
            n_csv = max(sum(1 for _ in f) - 1, 0)

    run_summary = {
        "primary_h5": str(args.primary_h5),
        "n_primary_exp_keys": len(primary_keys),
        "n_manifests_after_primary_filter": len(manifests),
        "seed_root": str(args.seed_root),
        "tracking_h5": str(args.tracking_h5),
        "manifest_path": str(args.manifest_path),
        "out_csv": str(csv_path),
        "models": list(models),
        "append": bool(args.append),
        "min_bout_frames": min_bout,
        "condition_layer": "run",
        "spot_definition": "mean(nose,neck,spine)/px_per_cm",
        "heading_source": "kpms results heading",
        "object_distance_cols": "nan (VAST has no fam/nvl objects)",
        "n_bout_rows_written_this_run": n_rows_total,
        "n_bout_rows_csv": n_csv,
        "elapsed_s": round(time.time() - t0, 1),
        "kinematics_fields": list(KINEMATICS_FIELDS),
        "per_model": per_model,
    }
    (out / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    (out / "INFO_syllable_kinematics.md").write_text(_info_md(), encoding="utf-8")
    (out / "cohort_primary_keys.json").write_text(
        json.dumps(
            {
                "primary_h5": str(args.primary_h5),
                "n_keys": len(primary_keys),
                "keys": sorted(primary_keys),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"Wrote {n_rows_total} bout rows this run "
        f"(csv total ~{n_csv}) -> {csv_path} ({run_summary['elapsed_s']}s)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
