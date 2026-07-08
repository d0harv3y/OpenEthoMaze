"""Align ``feedback/table`` to the ambulation xy video timeline."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import h5py
import numpy as np

from maze.core.h5_layout import read_feedback_table, resolve_ambulation_metrics_group, write_feedback_table
from maze.core.schema import FEEDBACK_ROW_DTYPE, XY_ROW_DTYPE
from maze.pipeline.db._shared import open_db
from maze.pipeline.db.trial_key import TrialKey

_DEFAULT_XY_POINT = "spot"
_RUN_RELATIVE_LEN_TOLERANCE = 2


def _decode_state(raw: object) -> str:
    if isinstance(raw, (bytes, np.bytes_)):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


def feedback_table_matches_xy(feedback: np.ndarray, xy: np.ndarray) -> bool:
    """True when feedback rows share xy ``frame_index`` and length."""
    if len(feedback) != len(xy):
        return False
    fi_fb = np.asarray(feedback["frame_index"], dtype=np.int64)
    fi_xy = np.asarray(xy["frame_index"], dtype=np.int64)
    return bool(np.array_equal(fi_fb, fi_xy))


def is_run_relative_legacy_feedback(
    feedback: np.ndarray,
    xy: np.ndarray,
    *,
    run_start_frame: int,
) -> bool:
    """Heuristic: run-only feedback with 0-based frame_index, shorter than xy."""
    if feedback_table_matches_xy(feedback, xy):
        return False
    n_video = len(xy)
    n_fb = len(feedback)
    if n_fb == 0 or n_fb > n_video:
        return False
    expected_run = n_video - int(run_start_frame)
    if abs(n_fb - expected_run) > _RUN_RELATIVE_LEN_TOLERANCE:
        return False
    fi = np.asarray(feedback["frame_index"], dtype=np.int64)
    return int(fi[0]) == 0 and bool(np.all(np.diff(fi) == 1))


def _blank_feedback_table(xy: np.ndarray) -> np.ndarray:
    n = len(xy)
    out = np.zeros(n, dtype=FEEDBACK_ROW_DTYPE)
    out["frame_index"] = np.asarray(xy["frame_index"], dtype=np.uint32)
    out["trial_state"] = xy["trial_state"]
    out["motor_fb"] = np.nan
    out["light_fb"] = np.nan
    out["sound_fb"] = 0.0
    return out


def _expand_run_relative_feedback(
    xy: np.ndarray,
    feedback: np.ndarray,
    *,
    run_start_frame: int,
) -> np.ndarray:
    out = _blank_feedback_table(xy)
    run_start = int(np.clip(run_start_frame, 0, len(xy)))
    n_copy = min(len(feedback), len(xy) - run_start)
    if n_copy <= 0:
        return out
    sl = slice(run_start, run_start + n_copy)
    out["motor_fb"][sl] = np.asarray(feedback["motor_fb"][:n_copy], dtype=np.float32)
    out["light_fb"][sl] = np.asarray(feedback["light_fb"][:n_copy], dtype=np.float32)
    return out


def _reindex_feedback_by_frame_index(feedback: np.ndarray, xy: np.ndarray) -> np.ndarray:
    out = _blank_feedback_table(xy)
    src_fi = np.asarray(feedback["frame_index"], dtype=np.int64)
    lookup = {int(fi): i for i, fi in enumerate(src_fi)}
    dst_fi = np.asarray(xy["frame_index"], dtype=np.int64)
    for i, fi in enumerate(dst_fi):
        j = lookup.get(int(fi))
        if j is None:
            continue
        out["motor_fb"][i] = feedback["motor_fb"][j]
        out["light_fb"][i] = feedback["light_fb"][j]
        out["trial_state"][i] = feedback["trial_state"][j]
    return out


def align_feedback_to_xy_table(
    xy: np.ndarray,
    feedback: np.ndarray,
    *,
    run_start_frame: int,
) -> np.ndarray:
    """Build a video-length feedback table aligned to ``xy`` rows."""
    xy = np.asarray(xy, dtype=XY_ROW_DTYPE)
    feedback = np.asarray(feedback, dtype=FEEDBACK_ROW_DTYPE)
    if feedback_table_matches_xy(feedback, xy):
        return feedback.copy()
    if is_run_relative_legacy_feedback(feedback, xy, run_start_frame=run_start_frame):
        return _expand_run_relative_feedback(xy, feedback, run_start_frame=run_start_frame)
    return _reindex_feedback_by_frame_index(feedback, xy)


def read_primary_xy_table(g_trial: h5py.Group, *, xy_point: str = _DEFAULT_XY_POINT) -> np.ndarray | None:
    g_amb = resolve_ambulation_metrics_group(g_trial)
    if g_amb is None:
        return None
    for point in (xy_point, "spot_hybrid", "spot", "centroid"):
        if point not in g_amb or "xy" not in g_amb[point]:
            continue
        rec = g_amb[point]["xy"][:]
        if rec.dtype != XY_ROW_DTYPE:
            continue
        return rec
    return None


def align_feedback_group(g_trial: h5py.Group, *, xy_point: str = _DEFAULT_XY_POINT) -> bool:
    """Rewrite ``feedback/table`` aligned to xy when needed. Returns True if rewritten."""
    xy = read_primary_xy_table(g_trial, xy_point=xy_point)
    if xy is None or len(xy) == 0:
        return False
    existing = read_feedback_table(g_trial)
    if existing is None or len(existing) == 0:
        return False
    if feedback_table_matches_xy(existing, xy):
        return False
    run_start = int(g_trial.attrs.get("trial_start_frame", 0) or 0)
    aligned = align_feedback_to_xy_table(xy, existing, run_start_frame=run_start)
    write_feedback_table(g_trial, aligned)
    return True


def align_feedback_for_trial(
    db_path: Path | str,
    key: TrialKey,
    *,
    xy_point: str = _DEFAULT_XY_POINT,
) -> bool:
    """Open H5 and align feedback for one trial. Returns True if rewritten."""
    with open_db(db_path, "a") as h5:
        path = key.path().lstrip("/")
        if path not in h5:
            return False
        return align_feedback_group(h5[path], xy_point=xy_point)


def align_feedback_h5(
    db_path: Path | str,
    *,
    keys: Optional[list[TrialKey]] = None,
    xy_point: str = _DEFAULT_XY_POINT,
) -> dict[str, int]:
    """Align all (or selected) trials in a cohort H5. Returns counts."""
    from maze.pipeline.db.trial_groups import list_trials

    db = Path(db_path)
    trial_keys = keys if keys is not None else list_trials(db)
    stats = {"seen": 0, "aligned": 0, "skipped": 0, "missing_xy": 0, "missing_feedback": 0}
    with open_db(db, "a") as h5:
        for key in trial_keys:
            stats["seen"] += 1
            path = key.path().lstrip("/")
            if path not in h5:
                stats["skipped"] += 1
                continue
            g = h5[path]
            xy = read_primary_xy_table(g, xy_point=xy_point)
            if xy is None:
                stats["missing_xy"] += 1
                continue
            existing = read_feedback_table(g)
            if existing is None:
                stats["missing_feedback"] += 1
                continue
            if feedback_table_matches_xy(existing, xy):
                stats["skipped"] += 1
                continue
            run_start = int(g.attrs.get("trial_start_frame", 0) or 0)
            aligned = align_feedback_to_xy_table(xy, existing, run_start_frame=run_start)
            write_feedback_table(g, aligned)
            stats["aligned"] += 1
    return stats
