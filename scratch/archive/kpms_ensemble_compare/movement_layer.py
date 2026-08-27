"""Movement-correlation layer for kpMS ensemble compare (scratch).

Joins legacy ambulation (``is_moving``, speed) to kpMS syllable rows via source
``frame_index`` alignment, then scores syllable bout boundaries against movement.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from maze.kpms.apply import KpmsApplyConfig
from maze.kpms.heading_idxs import PoseStream
from maze.kpms.h5_pose import (
    load_anatomical_from_h5,
    load_blob_from_h5,
    resolve_canonical_trial_h5,
)
from maze.kpms.preprocess import (
    KpmsPreprocessConfig,
    _fuse_anatomical_blob_tensors,
    _preprocess_h5_blob,
    _preprocess_h5_pose,
    _try_load_anatomical_tensors,
    _try_load_blob_tensors,
    finalize_kpms_recording_with_frame_indices,
)
from maze.pipeline.db.ambulation_xy import read_xy_table
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.db._shared import open_db
from maze.pipeline.io.file_discovery import TrialManifest

# Incomplete fits — exclude manually via ``--exclude-model`` in ``run_compare.py``.

DEFAULT_PREPROCESS = KpmsPreprocessConfig(
    min_fragment_frames=4,
    jump_filter_cm=15.0,
    jump_filter_lookahead_frames=3,
    px_per_cm=2.42,
    retain_all_frames=False,
    db_path=Path(r"C:\Users\admin\Documents\work\sack\test\kpms_tracking.h5"),
    pose_stream="anatomical",
)

DEFAULT_APPLY = KpmsApplyConfig(
    conf_threshold=0.2,
    min_points_per_frame=3,
    min_fragment_frames=4,
)

AMBULATION_POINT = "spot"  # legacy pipeline primary; centroid fallback in loader


@dataclass(frozen=True)
class MovementSeries:
    """Per kpMS row (length T), aligned to syllable vector."""

    source_frames: np.ndarray
    is_moving: np.ndarray
    speed_mps: np.ndarray
    abs_dspeed: np.ndarray


@dataclass(frozen=True)
class TrialMovementMetrics:
    trial_key: str
    model_id: str
    n_rows: int
    n_syllable_boundaries: int
    n_moving_boundaries: int
    boundary_vs_moving_f1: float
    boundary_vs_moving_precision: float
    boundary_vs_moving_recall: float
    mean_abs_dspeed_at_syllable_boundary: float
    mean_abs_dspeed_non_boundary: float
    boundary_dspeed_ratio: float


def syllable_boundaries(syll: np.ndarray) -> np.ndarray:
    s = np.asarray(syll, dtype=np.int64)
    if s.size < 2:
        return np.array([], dtype=np.int64)
    valid = (s[:-1] >= 0) & (s[1:] >= 0)
    changed = s[1:] != s[:-1]
    return (np.flatnonzero(valid & changed) + 1).astype(np.int64, copy=False)


def binary_run_boundaries(flags: np.ndarray) -> np.ndarray:
    """Change points for 0/1 (or bool) runs; indices are row positions."""
    f = np.asarray(flags, dtype=np.int8)
    if f.size < 2:
        return np.array([], dtype=np.int64)
    changed = f[1:] != f[:-1]
    return (np.flatnonzero(changed) + 1).astype(np.int64, copy=False)


def match_boundaries(b1: np.ndarray, b2: np.ndarray, delta: int) -> tuple[int, int, int]:
    if b1.size == 0 and b2.size == 0:
        return 0, 0, 0
    if b1.size == 0 or b2.size == 0:
        return 0, int(b1.size), int(b2.size)

    used_b2: set[int] = set()
    matched = 0
    for x in b1:
        best_j = None
        best_d = delta + 1
        for j, y in enumerate(b2):
            if j in used_b2:
                continue
            d = abs(int(x) - int(y))
            if d <= delta and d < best_d:
                best_d = d
                best_j = j
        if best_j is not None:
            used_b2.add(best_j)
            matched += 1
    return matched, int(b1.size), int(b2.size)


def boundary_prf(b1: np.ndarray, b2: np.ndarray, delta: int) -> tuple[float, float, float]:
    m, n1, n2 = match_boundaries(b1, b2, delta)
    if n1 == 0 and n2 == 0:
        return 1.0, 1.0, 1.0
    prec = m / n2 if n2 else 0.0
    rec = m / n1 if n1 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return prec, rec, f1


def _trial_key_from_manifest(manifest: TrialManifest) -> TrialKey:
    return TrialKey(
        animal_id=str(manifest.animal_id),
        session=str(manifest.h5_session),
        trial=str(manifest.trial),
    )


def _aligned_source_frames_h5(
    manifest: TrialManifest,
    pose_stream: PoseStream,
    pre_cfg: KpmsPreprocessConfig,
    apply_cfg: KpmsApplyConfig,
) -> np.ndarray | None:
    """Source video ``frame_index`` per kpMS syllable row (length T)."""
    del apply_cfg  # thresholds match finalize_kpms_recording_with_frame_indices defaults
    db_path = Path(pre_cfg.db_path) if pre_cfg.db_path else Path()

    if pose_stream == "fused":
        anat = _try_load_anatomical_tensors(manifest, db_path, pre_cfg)
        blob = _try_load_blob_tensors(manifest, db_path, pre_cfg)
        if anat is None and blob is None:
            return None
        fused_xy, fused_conf, fused_keep = _fuse_anatomical_blob_tensors(anat, blob)
        if int(fused_keep.sum()) < pre_cfg.min_fragment_frames:
            return None
        if anat is not None:
            a_fi = np.asarray(anat[0], dtype=np.uint32)
        elif blob is not None:
            a_fi = np.asarray(blob[0], dtype=np.uint32)
        else:
            return None
        if blob is not None and anat is None:
            frame_index = np.asarray(blob[0], dtype=np.uint32)
        elif anat is not None and blob is None:
            frame_index = a_fi
        else:
            a_fi = np.asarray(anat[0], dtype=np.uint32)
            b_fi = np.asarray(blob[0], dtype=np.uint32)
            frame_index = np.array(
                sorted(set(int(x) for x in a_fi) | set(int(x) for x in b_fi)),
                dtype=np.uint32,
            )
        fi = frame_index[fused_keep]
        coord = fused_xy[fused_keep]
        conf = fused_conf[fused_keep]
    elif pose_stream == "blob":
        canonical = resolve_canonical_trial_h5(manifest, db_path, pose_stream="blob")
        if canonical is None:
            return None
        pose = load_blob_from_h5(canonical, _trial_key_from_manifest(manifest))
        if pose is None:
            return None
        arr_xy, arr_conf, keep = _preprocess_h5_blob(pose, pre_cfg)
        fi = np.asarray(pose.frame_index, dtype=np.uint32)[keep]
        coord = arr_xy[keep]
        conf = arr_conf[keep]
    else:
        canonical = resolve_canonical_trial_h5(manifest, db_path, pose_stream="anatomical")
        if canonical is None:
            return None
        pose = load_anatomical_from_h5(canonical, _trial_key_from_manifest(manifest))
        if pose is None:
            return None
        arr_xy, arr_conf, keep = _preprocess_h5_pose(pose, pre_cfg)
        fi = np.asarray(pose.frame_index, dtype=np.uint32)[keep]
        coord = arr_xy[keep]
        conf = arr_conf[keep]

    finalized = finalize_kpms_recording_with_frame_indices(coord, conf, fi, pre_cfg)
    if finalized is None:
        return None
    return finalized[2].astype(np.uint32, copy=False)


def load_ambulation_xy(
    legacy_db: Path,
    manifest: TrialManifest,
    *,
    point: str = AMBULATION_POINT,
) -> np.ndarray | None:
    key = _trial_key_from_manifest(manifest)
    xy = read_xy_table(legacy_db, key, point)
    if xy is not None:
        return xy
    if point != "centroid":
        return read_xy_table(legacy_db, key, "centroid")
    return None


def _trial_px_per_cm(legacy_db: Path, manifest: TrialManifest) -> float:
    """Read per-trial calibration from legacy H5 (fallback: DEFAULT_PREPROCESS px_per_cm)."""
    key = _trial_key_from_manifest(manifest)
    try:
        with open_db(legacy_db, "r") as h5:
            ppc = float(h5[key.path()].attrs.get("px_per_cm", 0.0))
            if ppc > 0:
                return ppc
    except (KeyError, OSError, TypeError, ValueError):
        pass
    return float(DEFAULT_PREPROCESS.px_per_cm)


def _speed_from_xy(xy: np.ndarray, *, px_per_cm: float) -> tuple[np.ndarray, np.ndarray]:
    """Return (frame_index, speed_mps) on ambulation rows; speed[0]=0.

    ``xy['x']`` / ``xy['y']`` are **pixels** (``maze.core.schema.XY_ROW_DTYPE``).
    """
    fi = np.asarray(xy["frame_index"], dtype=np.int64)
    x = np.asarray(xy["x"], dtype=np.float64)
    y = np.asarray(xy["y"], dtype=np.float64)
    t = np.asarray(xy["t_s"], dtype=np.float64)
    speed = np.zeros(fi.shape[0], dtype=np.float64)
    if fi.size >= 2:
        dt = np.diff(t)
        dt = np.where(dt > 0, dt, np.nan)
        dist_px = np.hypot(np.diff(x), np.diff(y))
        px_per_m = max(float(px_per_cm) * 100.0, 1e-9)
        dist_m = dist_px / px_per_m
        spd = dist_m / dt
        speed[1:] = np.nan_to_num(spd, nan=0.0)
    return fi, speed


def movement_series_for_trial(
    manifest: TrialManifest,
    pose_stream: PoseStream,
    legacy_db: Path,
    *,
    pre_cfg: KpmsPreprocessConfig | None = None,
    apply_cfg: KpmsApplyConfig | None = None,
) -> MovementSeries | None:
    pre = pre_cfg or DEFAULT_PREPROCESS
    apply = apply_cfg or DEFAULT_APPLY
    stream_cfg = KpmsPreprocessConfig(
        min_fragment_frames=pre.min_fragment_frames,
        jump_filter_cm=pre.jump_filter_cm,
        jump_filter_lookahead_frames=pre.jump_filter_lookahead_frames,
        px_per_cm=pre.px_per_cm,
        retain_all_frames=pre.retain_all_frames,
        db_path=pre.db_path,
        pose_stream=pose_stream,
    )
    row_frames = _aligned_source_frames_h5(manifest, pose_stream, stream_cfg, apply)
    if row_frames is None:
        return None

    xy = load_ambulation_xy(legacy_db, manifest)
    if xy is None:
        return None

    px_per_cm = _trial_px_per_cm(legacy_db, manifest)

    amb_fi = np.asarray(xy["frame_index"], dtype=np.int64)
    amb_moving = np.asarray(xy["is_moving"], dtype=np.uint8)
    amb_fi_speed, amb_speed = _speed_from_xy(xy, px_per_cm=px_per_cm)

    fi_to_moving = {int(f): int(m) for f, m in zip(amb_fi, amb_moving, strict=True)}
    fi_to_speed = {int(f): float(s) for f, s in zip(amb_fi_speed, amb_speed, strict=True)}

    is_moving = np.array([fi_to_moving.get(int(f), 0) for f in row_frames], dtype=np.uint8)
    speed = np.array([fi_to_speed.get(int(f), 0.0) for f in row_frames], dtype=np.float64)
    dspeed = np.zeros_like(speed)
    if speed.size >= 2:
        dspeed[1:] = np.abs(np.diff(speed))

    return MovementSeries(
        source_frames=row_frames,
        is_moving=is_moving,
        speed_mps=speed,
        abs_dspeed=dspeed,
    )


def trial_movement_metrics(
    syll: np.ndarray,
    movement: MovementSeries,
    *,
    delta: int = 3,
) -> TrialMovementMetrics | None:
    syll = np.asarray(syll)
    if syll.shape[0] != movement.source_frames.shape[0]:
        return None

    row_syll_b = syllable_boundaries(syll)
    row_move_b = binary_run_boundaries(movement.is_moving)

    src_syll_b = movement.source_frames[row_syll_b].astype(np.int64, copy=False)
    src_move_b = movement.source_frames[row_move_b].astype(np.int64, copy=False)

    prec, rec, f1 = boundary_prf(src_syll_b, src_move_b, delta)

    boundary_mask = np.zeros(syll.shape[0], dtype=bool)
    if row_syll_b.size:
        boundary_mask[row_syll_b] = True
    ds = movement.abs_dspeed
    at_b = float(np.mean(ds[boundary_mask])) if boundary_mask.any() else 0.0
    off_b = float(np.mean(ds[~boundary_mask])) if (~boundary_mask).any() else 0.0
    ratio = at_b / off_b if off_b > 1e-12 else float("nan")

    return TrialMovementMetrics(
        trial_key="",
        model_id="",
        n_rows=int(syll.shape[0]),
        n_syllable_boundaries=int(src_syll_b.size),
        n_moving_boundaries=int(src_move_b.size),
        boundary_vs_moving_f1=f1,
        boundary_vs_moving_precision=prec,
        boundary_vs_moving_recall=rec,
        mean_abs_dspeed_at_syllable_boundary=at_b,
        mean_abs_dspeed_non_boundary=off_b,
        boundary_dspeed_ratio=ratio,
    )


def aggregate_movement_metrics(
    models: list,
    results_by_model: dict[str, dict],
    manifest_by_key: dict[str, TrialManifest],
    legacy_db: Path,
    *,
    delta: int = 3,
    exclude_models: frozenset[str] | None = None,
    tracking_db: Path | None = None,
) -> tuple[list[dict], list[dict]]:
    """Return (per_model_summary_rows, per_trial_rows)."""
    exclude = exclude_models if exclude_models is not None else frozenset()
    pre_cfg = DEFAULT_PREPROCESS
    if tracking_db is not None:
        pre_cfg = KpmsPreprocessConfig(
            min_fragment_frames=pre_cfg.min_fragment_frames,
            jump_filter_cm=pre_cfg.jump_filter_cm,
            jump_filter_lookahead_frames=pre_cfg.jump_filter_lookahead_frames,
            px_per_cm=pre_cfg.px_per_cm,
            retain_all_frames=pre_cfg.retain_all_frames,
            db_path=tracking_db,
            pose_stream=pre_cfg.pose_stream,
        )

    trial_cache: dict[tuple[str, str], MovementSeries | None] = {}
    per_trial: list[dict] = []
    per_model_acc: dict[str, list[TrialMovementMetrics]] = defaultdict(list)

    for model in models:
        if model.model_id in exclude:
            continue
        pose_stream: PoseStream = model.stream  # type: ignore[assignment]

        for trial_key, rec in results_by_model[model.model_id].items():
            manifest = manifest_by_key.get(trial_key)
            if manifest is None:
                continue

            cache_key = (trial_key, pose_stream)
            if cache_key not in trial_cache:
                trial_cache[cache_key] = movement_series_for_trial(
                    manifest, pose_stream, legacy_db, pre_cfg=pre_cfg
                )
            movement = trial_cache[cache_key]
            if movement is None:
                continue

            m = trial_movement_metrics(np.asarray(rec["syllable"]), movement, delta=delta)
            if m is None:
                continue
            per_trial.append(
                {
                    "trial_key": trial_key,
                    "model_id": model.model_id,
                    "stream": model.stream,
                    "n_rows": m.n_rows,
                    "n_syllable_boundaries": m.n_syllable_boundaries,
                    "n_moving_boundaries": m.n_moving_boundaries,
                    "boundary_vs_moving_f1": m.boundary_vs_moving_f1,
                    "boundary_vs_moving_precision": m.boundary_vs_moving_precision,
                    "boundary_vs_moving_recall": m.boundary_vs_moving_recall,
                    "mean_abs_dspeed_at_boundary": m.mean_abs_dspeed_at_syllable_boundary,
                    "mean_abs_dspeed_non_boundary": m.mean_abs_dspeed_non_boundary,
                    "boundary_dspeed_ratio": m.boundary_dspeed_ratio,
                }
            )
            per_model_acc[model.model_id].append(m)

    summary: list[dict] = []
    for model_id, rows in sorted(per_model_acc.items()):
        f1s = [r.boundary_vs_moving_f1 for r in rows]
        ratios = [r.boundary_dspeed_ratio for r in rows if np.isfinite(r.boundary_dspeed_ratio)]
        stream = model_id.split("/")[0]
        fracs = []
        for trial_key in manifest_by_key:
            mv = trial_cache.get((trial_key, stream))
            if mv is not None:
                fracs.append(float(np.mean(mv.is_moving)))
        summary.append(
            {
                "model_id": model_id,
                "n_trials": len(rows),
                "median_boundary_vs_moving_f1": float(np.median(f1s)),
                "mean_boundary_vs_moving_f1": float(np.mean(f1s)),
                "median_boundary_dspeed_ratio": float(np.median(ratios)) if ratios else float("nan"),
                "mean_fraction_moving": float(np.mean(fracs)) if fracs else float("nan"),
            }
        )

    return summary, per_trial
