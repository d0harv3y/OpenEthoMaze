from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from maze.core.schema import NODE_SUMMARY_BY_STATE_DTYPE, NODE_SUMMARY_DTYPE

from ._shared import ensure_group, open_db, safe_str
from .trial_key import TrialKey


def node_summary_dtype() -> np.dtype:
    """Structured dtype for per-node summary (shared maze.core schema)."""
    return NODE_SUMMARY_DTYPE


def node_summary_by_state_dtype() -> np.dtype:
    """Structured dtype for per-node summary split by trial-state band."""
    return NODE_SUMMARY_BY_STATE_DTYPE


def write_node_summary_by_state(
    db_path: Optional[Path],
    key: TrialKey,
    point_name: str,
    summaries: list[dict[str, Any]],
) -> None:
    """Write banded ambulation and exit summaries for a tracking point."""
    if db_path is None or not summaries:
        return
    base = NODE_SUMMARY_DTYPE
    arr = np.zeros((len(summaries),), dtype=NODE_SUMMARY_BY_STATE_DTYPE)
    for i, summary in enumerate(summaries):
        arr["trial_state"][i] = safe_str(summary.get("trial_state", "")).encode("utf-8")
        for name in base.names:
            if name in summary:
                arr[name][i] = summary[name]
    with open_db(db_path, "a") as h5:
        g_pt = ensure_group(ensure_group(h5[key.path()], "ambulation_metrics"), point_name)
        for old_name in ("summary", "summary_by_state"):
            if old_name in g_pt:
                del g_pt[old_name]
        g_pt.create_dataset("summary", data=arr, compression="gzip")


def _summary_run_row(g_pt: Any) -> Optional[np.ndarray]:
    """Pick the analysis-window ``run`` row from a banded summary dataset."""
    if "summary" not in g_pt:
        return None
    arr = g_pt["summary"][:]
    if arr.shape[0] == 0:
        return None
    names = arr.dtype.names or ()
    if "trial_state" not in names:
        return arr[0]
    for i in range(arr.shape[0]):
        ts = arr["trial_state"][i]
        if isinstance(ts, bytes):
            ts = ts.decode("utf-8", errors="replace").strip()
        else:
            ts = str(ts).strip()
        if ts == "run":
            return arr[i]
    return arr[arr.shape[0] - 1]


def read_exit_metrics(
    db_path: Optional[Path],
    key: TrialKey,
    point_name: str = "spot",
) -> Optional[np.ndarray]:
    """Read exit metrics for a trial from ``ambulation_metrics/<point>/summary``."""
    try:
        with open_db(db_path, "r") as h5:
            summary = _summary_run_row(h5[key.path()]["ambulation_metrics"][point_name])
            if summary is None:
                return None
            out = np.zeros((1,), dtype=exit_metrics_dtype())
            for name in out.dtype.names:
                out[name] = summary[name]
            return out
    except (KeyError, ValueError):
        return None


def exit_metrics_dtype() -> np.dtype:
    """Structured dtype for exit metrics (subset of node summary)."""
    return np.dtype(
        [
            ("latency_to_exit_s", np.float64),
            ("time_in_exit_zone_s", np.float64),
            ("time_in_exit_zone_fraction", np.float64),
            ("mean_distance_to_exit_cm", np.float64),
            ("min_distance_to_exit_cm", np.float64),
            ("path_efficiency", np.float64),
            ("n_exit_zone_entries", np.int32),
        ]
    )


def ambulation_summary_dtype() -> np.dtype:
    """Structured dtype for ambulation-only summary (subset of node summary)."""
    return np.dtype(
        [
            ("total_distance_m", np.float64),
            ("mean_speed_mps", np.float64),
            ("max_speed_mps", np.float64),
            ("time_moving_s", np.float64),
            ("time_immobile_s", np.float64),
            ("n_movement_bouts", np.int32),
        ]
    )
