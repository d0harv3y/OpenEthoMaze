"""
HDF5 database module for VAST pipeline.

Handles reading and writing trial data to the output HDF5 database.

Output Structure:
    vast_results.h5
    ├── metadata/
    │   ├── config_snapshot (attrs)
    │   ├── trial_manifest (dataset: manifest CSV columns)
    │   └── animal_labels/
    ├── {animal_id}/
    │   └── {session}/   (e.g. S01, H01 for habituation)
    │       └── {trial}/
    │               ├── attrs: video_path, sleap_path, sleap_model_path, primary_trajectory, timestamp, etc.
    │               ├── ambulation_metrics/
    │               │   ├── spot/   [xy, movement_bouts, summary (banded: iti_wait, run)]
    │               │   ├── centroid/
    │               │   └── in-range/   [xy, movement_bouts, summary] (controller/legacy fallback)
    │               └── qc_images/
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from datetime import datetime
    from ..io.file_discovery import TrialManifest

import h5py
import numpy as np

from vast.core.schema import (
    XY_ROW_DTYPE,
    NODE_SUMMARY_DTYPE,
    NODE_SUMMARY_BY_STATE_DTYPE,
    FEEDBACK_ROW_DTYPE,
    FEEDBACK_GROUP,
)
from vast.core.storage import (
    open_db as core_open_db,
    write_xy_table as core_write_xy_table,
    write_feedback_table as core_write_feedback_table,
    read_feedback_table as core_read_feedback_table,
)
from ..config import OUTPUT_H5, get_config_snapshot
from ..config import QC_IMAGE_STORE_FORMAT


@dataclass(frozen=True)
class TrialKey:
    """Unique identifier for a trial in the database.
    Path is /animal_id/session/trial (no phase level). Phase is derived from session (H-prefix = habituation).
    """
    animal_id: str
    session: str  # e.g. "S01", "H01" (H = habituation)
    trial: str    # e.g. "T01"

    def path(self) -> str:
        """HDF5 group path for this trial."""
        return f"/{self.animal_id}/{self.session}/{self.trial}"

    @property
    def phase(self) -> str:
        """'habituation' if session starts with H, else 'experimental' (for filtering/display)."""
        return "habituation" if self.session.upper().startswith("H") else "experimental"

    @classmethod
    def from_manifest(cls, manifest: "TrialManifest") -> "TrialKey":
        """Create TrialKey from a TrialManifest."""
        return cls(
            animal_id=manifest.animal_id,
            session=manifest.session,
            trial=manifest.trial,
        )


def _ensure_group(parent: h5py.Group, name: str) -> h5py.Group:
    """Get or create a group."""
    return parent[name] if name in parent else parent.create_group(name)


def _write_json_attr(g: h5py.Group, key: str, obj: Any) -> None:
    """Write a JSON-serializable object as an attribute."""
    g.attrs[key] = json.dumps(obj, ensure_ascii=False)


def _safe_str(x: Any) -> str:
    """Convert value to string safely."""
    return "" if x is None else str(x)


def open_db(db_path: Optional[Path] = None, mode: str = "a") -> h5py.File:
    """
    Open the HDF5 database file using shared vast.core.storage.open_db.
    """
    path = db_path or OUTPUT_H5
    return core_open_db(Path(path), mode)  # type: ignore[name-defined]


def init_database(db_path: Optional[Path] = None) -> None:
    """
    Initialize the database with metadata structure.
    
    Args:
        db_path: Path to database (uses config default if None)
    """
    with open_db(db_path, "a") as h5:
        meta = _ensure_group(h5, "metadata")
        
        # Write config snapshot
        _write_json_attr(meta, "config_snapshot", get_config_snapshot())
        
        # Create animal_labels group for future treatment labels
        _ensure_group(meta, "animal_labels")
        
        # Arena info placeholder
        arena = _ensure_group(meta, "arena_info")
        arena.attrs["type"] = "circular"
        arena.attrs["description"] = "Circular open field with distance-proportional vibration feedback"


def ensure_trial_group(
    db_path: Optional[Path],
    key: TrialKey,
    video_path: Optional[str] = None,
    sleap_path: Optional[str] = None,
    input_h5_path: Optional[str] = None,
    sleap_model_path: Optional[str] = None,
) -> None:
    """
    Ensure trial group exists and set basic attributes.
    
    Args:
        db_path: Path to database
        key: Trial key
        video_path: Path to video file
        sleap_path: Path to SLEAP file
        input_h5_path: Path to input H5 file
        sleap_model_path: Path to SLEAP model used for inference (optional)
    """
    with open_db(db_path, "a") as h5:
        # Create group hierarchy: animal_id / session / trial (no phase level)
        g_animal = _ensure_group(h5, key.animal_id)
        g_session = _ensure_group(g_animal, key.session)
        g_trial = _ensure_group(g_session, key.trial)
        
        # Set file paths
        if video_path is not None:
            g_trial.attrs["video_path"] = _safe_str(video_path)
        if sleap_path is not None:
            g_trial.attrs["sleap_path"] = _safe_str(sleap_path)
        if input_h5_path is not None:
            g_trial.attrs["input_h5_path"] = _safe_str(input_h5_path)
        if sleap_model_path is not None:
            g_trial.attrs["sleap_model_path"] = _safe_str(sleap_model_path)
        
        # Ensure sub-groups exist
        _ensure_group(g_trial, "ambulation_metrics")
        _ensure_group(g_trial, "qc_images")


def write_trial_settings(
    db_path: Optional[Path],
    key: TrialKey,
    arena_radius_px: float,
    px_per_cm: float,
    arena_center_x_px: Optional[float] = None,
    arena_center_y_px: Optional[float] = None,
    timestamp: Optional[str] = None,
    stage: Optional[str] = None,
    color: Optional[str] = None,
    exit_number: Optional[int] = None,
    exit_x: Optional[float] = None,
    exit_y: Optional[float] = None,
    roi_old: Optional[str] = None,
    h5_fps: Optional[float] = None,
    trial_start_frame: Optional[int] = None,
) -> None:
    """
    Write trial settings (exit position, arena geometry) to database.

    Args:
        db_path: Path to database
        key: Trial key
        arena_radius_px: Arena radius in pixels
        px_per_cm: Calibration factor
        arena_center_x_px, arena_center_y_px: Arena center in pixels (from ROI string)
        timestamp: Recording timestamp
        stage: Task stage
        color: Vibration color/intensity setting
        exit_number: Exit hole number (from settings array)
        exit_x, exit_y: Exit coordinates (from settings array)
        roi_old: Original ROI string for verification
        h5_fps: FPS derived from input H5 timer0 array
        trial_start_frame: First frame where subtrial==1 (analysis start after ITI)
    """
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]

        g_trial.attrs["arena_radius_px"] = float(arena_radius_px)
        g_trial.attrs["px_per_cm"] = float(px_per_cm)

        if arena_center_x_px is not None:
            g_trial.attrs["arena_center_x_px"] = float(arena_center_x_px)
        if arena_center_y_px is not None:
            g_trial.attrs["arena_center_y_px"] = float(arena_center_y_px)
        if timestamp is not None:
            g_trial.attrs["timestamp"] = _safe_str(timestamp)
        if stage is not None:
            g_trial.attrs["stage"] = _safe_str(stage)
        if color is not None:
            g_trial.attrs["color"] = _safe_str(color)
        if exit_number is not None:
            g_trial.attrs["exit_number"] = int(exit_number)
        if exit_x is not None:
            g_trial.attrs["exit_x"] = float(exit_x)
        if exit_y is not None:
            g_trial.attrs["exit_y"] = float(exit_y)
        if roi_old is not None:
            g_trial.attrs["roi_old"] = _safe_str(roi_old)
        if h5_fps is not None:
            g_trial.attrs["h5_fps"] = float(h5_fps)
        if trial_start_frame is not None:
            g_trial.attrs["trial_start_frame"] = int(trial_start_frame)


def write_feedback_series(
    db_path: Optional[Path],
    key: TrialKey,
    w: np.ndarray,
    m: np.ndarray,
    trial_start_frame: Optional[int] = None,
) -> None:
    """
    Legacy API: write W (white light) and M (motor) feedback series.

    New schema stores a unified feedback/table with FEEDBACK_ROW_DTYPE where
    motor_fb is the primary feedback channel and light_fb/sound_fb are optional.
    This function now writes the unified table while preserving its original
    signature so existing scripts (init_db, sync_db) continue to work.

    If trial_start_frame is provided, frames before it are marked "iti_wait", rest "run".
    """
    w = np.asarray(w, dtype=np.float32)
    m = np.asarray(m, dtype=np.float32)
    if len(w) != len(m):
        raise ValueError("write_feedback_series: w and m must have the same length")
    n = len(m)
    if n == 0:
        return
    fb = np.zeros(n, dtype=FEEDBACK_ROW_DTYPE)
    fb["frame_index"] = np.arange(n, dtype=np.uint32)
    if trial_start_frame is not None and trial_start_frame > 0 and trial_start_frame < n:
        fb["trial_state"][:trial_start_frame] = b"iti_wait"
        fb["trial_state"][trial_start_frame:] = b"run"
    else:
        fb["trial_state"] = b"run"
    # Store motor feedback in motor_fb; keep light_fb as legacy W for compatibility.
    fb["motor_fb"] = m
    fb["light_fb"] = w
    fb["sound_fb"] = 0.0
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        core_write_feedback_table(g_trial, fb)


def read_feedback_series(
    db_path: Optional[Path],
    key: TrialKey,
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """
    Read feedback W and M series for a trial. Returns (w, m) or None if missing.

    Supports both the legacy /feedback/w,/feedback/m datasets and the new
    unified /feedback/table dataset written by vast_controller.
    """
    try:
        with open_db(db_path, "r") as h5:
            g_trial = h5[key.path()]
            g_fb = g_trial.get(FEEDBACK_GROUP)
            if g_fb is None:
                return None
            # Preferred: unified feedback/table.
            fb_table = core_read_feedback_table(g_trial)
            if fb_table is not None:
                m = np.asarray(fb_table["motor_fb"], dtype=np.float64)
                # For backwards compatibility, expose light_fb as w; fall back to zeros.
                if "light_fb" in fb_table.dtype.names:
                    w = np.asarray(fb_table["light_fb"], dtype=np.float64)
                else:
                    w = np.zeros_like(m)
                return (w, m)
            # Legacy: separate w/m datasets.
            if "w" in g_fb and "m" in g_fb:
                w = np.asarray(g_fb["w"][:], dtype=np.float64)
                m = np.asarray(g_fb["m"][:], dtype=np.float64)
                return (w, m)
            return None
    except (KeyError, ValueError, OSError):
        return None


def write_feedback_error_summary(
    db_path: Optional[Path],
    key: TrialKey,
    n_incongruent_bouts: int,
    incongruent_duration_s: float,
) -> None:
    """
    Write feedback error (incongruent feedback) summary to the trial feedback group.

    Incongruent = feedback and distance-to-exit change in the same direction
    (e.g. moving away from exit but feedback increasing). Stored as attrs on
    the feedback group.
    """
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_fb = _ensure_group(g_trial, "feedback")
        g_fb.attrs["n_incongruent_bouts"] = int(n_incongruent_bouts)
        g_fb.attrs["incongruent_duration_s"] = float(incongruent_duration_s)


def read_trial_settings(
    db_path: Optional[Path],
    key: TrialKey,
) -> tuple:
    """
    Read trial settings from the output database.

    Returns (TrialSettings, h5_fps, trial_start_frame). TrialSettings is
    reconstructed from the attrs written by write_trial_settings(). h5_fps
    may be None if not stored. trial_start_frame defaults to 0 if not stored.

    Args:
        db_path: Path to database
        key: Trial key

    Returns:
        Tuple of (TrialSettings, h5_fps, trial_start_frame)

    Raises:
        KeyError: If trial group doesn't exist
    """
    from ..io.input_h5_loader import TrialSettings, parse_timestamp

    with open_db(db_path, "r") as h5:
        g_trial = h5[key.path()]
        attrs = g_trial.attrs

        # Parse timestamp back to datetime if present
        timestamp_str = attrs.get("timestamp", None)
        if isinstance(timestamp_str, bytes):
            timestamp_str = timestamp_str.decode("utf-8")
        timestamp = parse_timestamp(timestamp_str) if timestamp_str else None

        # Decode byte strings
        stage = attrs.get("stage", "")
        if isinstance(stage, bytes):
            stage = stage.decode("utf-8")
        color = attrs.get("color", "")
        if isinstance(color, bytes):
            color = color.decode("utf-8")
        roi_old = attrs.get("roi_old", None)
        if isinstance(roi_old, bytes):
            roi_old = roi_old.decode("utf-8")

        settings = TrialSettings(
            arena_center_x_px=float(attrs.get("arena_center_x_px", 0.0)),
            arena_center_y_px=float(attrs.get("arena_center_y_px", 0.0)),
            arena_radius_px=float(attrs["arena_radius_px"]),
            px_per_cm=float(attrs["px_per_cm"]),
            stage=stage,
            color=color,
            timestamp=timestamp,
            exit_number=int(attrs["exit_number"]) if "exit_number" in attrs else None,
            exit_x=float(attrs["exit_x"]) if "exit_x" in attrs else None,
            exit_y=float(attrs["exit_y"]) if "exit_y" in attrs else None,
            roi_old=roi_old,
        )

        h5_fps = float(attrs["h5_fps"]) if "h5_fps" in attrs else None
        trial_start_frame = int(attrs["trial_start_frame"]) if "trial_start_frame" in attrs else 0

    return settings, h5_fps, trial_start_frame


def read_trial_meta_for_manifest(
    db_path: Optional[Path], key: TrialKey
) -> tuple[Optional[datetime], Optional[int]]:
    """
    Read timestamp and n_frames from trial attrs for manifest backfill.
    Returns (timestamp, n_frames); timestamp is datetime or None, n_frames is int or None.
    """
    try:
        with open_db(db_path, "r") as h5:
            g_trial = h5[key.path()]
            attrs = g_trial.attrs
            ts_str = attrs.get("timestamp", None)
            if isinstance(ts_str, bytes):
                ts_str = ts_str.decode("utf-8")
            from ..io.input_h5_loader import parse_timestamp
            timestamp = parse_timestamp(ts_str) if ts_str else None
            n_frames = int(attrs["n_frames"]) if "n_frames" in attrs else None
        return (timestamp, n_frames)
    except (KeyError, ValueError, TypeError):
        return (None, None)


def write_trial_frame_counts(
    db_path: Optional[Path],
    key: TrialKey,
    h5_n_frames: int,
    video_n_frames: int,
) -> None:
    """Write H5 and video frame counts to trial attributes (for frame_diff filtering)."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_trial.attrs["h5_n_frames"] = int(h5_n_frames)
        g_trial.attrs["video_n_frames"] = int(video_n_frames)


def write_video_meta(
    db_path: Optional[Path],
    key: TrialKey,
    fps: float,
    n_frames: int,
    duration_s: float,
) -> None:
    """Write video metadata to trial attributes."""
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_trial.attrs["fps"] = float(fps)
        g_trial.attrs["n_frames"] = int(n_frames)
        g_trial.attrs["duration_s"] = float(duration_s)


def write_analysis_duration(
    db_path: Optional[Path],
    key: TrialKey,
    analysis_duration_s: float,
) -> None:
    """Write analysis-window duration (excludes ITI) for reporting."""
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_trial.attrs["analysis_duration_s"] = float(analysis_duration_s)


def write_primary_trajectory(
    db_path: Optional[Path],
    key: TrialKey,
    primary_trajectory: str,
) -> None:
    """Write which trajectory is primary for export (spot or in-range)."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_trial.attrs["primary_trajectory"] = _safe_str(primary_trajectory)


def write_mistrial_reason(
    db_path: Optional[Path],
    key: TrialKey,
    reason: str,
) -> None:
    """Write mistrial reason to trial attributes (e.g. missing_video, missing_sleap)."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_trial.attrs["mistrial_reason"] = _safe_str(reason)


def write_sleap_path(
    db_path: Optional[Path],
    key: TrialKey,
    sleap_path: str,
) -> None:
    """Write the path to the SLEAP predictions file (.slp) to trial attributes."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_trial.attrs["sleap_path"] = _safe_str(sleap_path)


def write_sleap_model_path(
    db_path: Optional[Path],
    key: TrialKey,
    model_path: str,
) -> None:
    """Write the SLEAP model path used for inference to trial attributes."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_trial.attrs["sleap_model_path"] = _safe_str(model_path)


# =============================================================================
# XY Table (position data)
# =============================================================================

def xy_table_dtype() -> np.dtype:
    """Structured dtype for XY position table (shared vast.core schema)."""
    return XY_ROW_DTYPE


def write_xy_table(
    db_path: Optional[Path],
    key: TrialKey,
    point_name: str,
    xy_table: np.ndarray,
    fps: float,
) -> None:
    """
    Write XY position table to database.
    
    Args:
        db_path: Path to database
        key: Trial key
        point_name: Tracking point name (e.g., "spot", "centroid", "nose")
        xy_table: Structured array with xy_table_dtype
        fps: Video FPS
    """
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        core_write_xy_table(g_trial, point_name, xy_table, fps)


def read_xy_table(
    db_path: Optional[Path],
    key: TrialKey,
    point_name: str,
) -> Optional[np.ndarray]:
    """Read XY table for a tracking point."""
    try:
        with open_db(db_path, "r") as h5:
            g_trial = h5[key.path()]
            return g_trial["ambulation_metrics"][point_name]["xy"][:]
    except (KeyError, ValueError):
        return None


# =============================================================================
# Movement Bouts
# =============================================================================

def movement_bout_dtype() -> np.dtype:
    """Structured dtype for movement bout data."""
    return np.dtype([
        ("start_frame", np.int32),
        ("end_frame", np.int32),
        ("duration_frames", np.int32),
        ("duration_s", np.float32),
        ("total_distance_m", np.float32),
        ("mean_speed_mps", np.float32),
        ("max_speed_mps", np.float32),
    ])


def write_movement_bouts(
    db_path: Optional[Path],
    key: TrialKey,
    point_name: str,
    bouts: list[dict[str, Any]],
    analysis_start_frame: int = 0,
) -> None:
    """
    Write movement bouts to database.
    Bout start/end are stored as video frame indices (analysis_start_frame + bout index)
    so that all stored frames are in the analysis window (ITI excluded).
    """
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_amb = _ensure_group(g_trial, "ambulation_metrics")
        g_pt = _ensure_group(g_amb, point_name)

        if not bouts:
            if "movement_bouts" in g_pt:
                del g_pt["movement_bouts"]
            g_pt.create_dataset(
                "movement_bouts",
                data=np.array([], dtype=movement_bout_dtype()),
                compression="gzip"
            )
            g_pt.attrs["analysis_start_frame"] = int(analysis_start_frame)
            return

        # Convert bout indices (analysis-window relative) to video frame indices (ITI excluded)
        bout_array = np.zeros((len(bouts),), dtype=movement_bout_dtype())
        for i, bout in enumerate(bouts):
            bout_array[i]["start_frame"] = int(analysis_start_frame + bout.get("start_frame", 0))
            bout_array[i]["end_frame"] = int(analysis_start_frame + bout.get("end_frame", 0))
            bout_array[i]["duration_frames"] = int(bout.get("duration_frames", 0))
            bout_array[i]["duration_s"] = float(bout.get("duration_s", 0.0))
            bout_array[i]["total_distance_m"] = float(bout.get("total_distance_m", 0.0))
            bout_array[i]["mean_speed_mps"] = float(bout.get("mean_speed_mps", 0.0))
            bout_array[i]["max_speed_mps"] = float(bout.get("max_speed_mps", 0.0))
        
        if "movement_bouts" in g_pt:
            del g_pt["movement_bouts"]
        g_pt.create_dataset("movement_bouts", data=bout_array, compression="gzip")
        g_pt.attrs["analysis_start_frame"] = int(analysis_start_frame)


# =============================================================================
# Node Summary (ambulation + exit metrics per tracking point)
# =============================================================================

def node_summary_dtype() -> np.dtype:
    """Structured dtype for per-node summary (shared vast.core schema)."""
    return NODE_SUMMARY_DTYPE


def node_summary_by_state_dtype() -> np.dtype:
    """Structured dtype for per-node summary split by trial_state band (iti_wait vs run)."""
    return NODE_SUMMARY_BY_STATE_DTYPE


def write_node_summary_by_state(
    db_path: Optional[Path],
    key: TrialKey,
    point_name: str,
    summaries: list[dict[str, Any]],
) -> None:
    """
    Write banded ambulation + exit summary for a tracking point to
    ambulation_metrics/<point_name>/summary (multi-row: iti_wait, run, …).

    Each element of `summaries` should contain:
      - trial_state: str (e.g. \"iti_wait\" or \"run\")
      - all fields expected by node_summary_dtype().
    """
    if db_path is None or not summaries:
        return
    base = NODE_SUMMARY_DTYPE
    dt = NODE_SUMMARY_BY_STATE_DTYPE
    arr = np.zeros((len(summaries),), dtype=dt)
    for i, summary in enumerate(summaries):
        ts = _safe_str(summary.get("trial_state", ""))
        arr["trial_state"][i] = ts.encode("utf-8")
        for name in base.names:
            if name in summary:
                arr[name][i] = summary[name]
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_amb = _ensure_group(g_trial, "ambulation_metrics")
        g_pt = _ensure_group(g_amb, point_name)
        for old_name in ("summary", "summary_by_state"):
            if old_name in g_pt:
                del g_pt[old_name]
        g_pt.create_dataset("summary", data=arr, compression="gzip")


def _summary_run_row(g_pt: Any) -> Optional[np.ndarray]:
    """Pick the analysis-window (run) row from a banded summary dataset, if present."""
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
    """
    Read exit metrics for a trial from ambulation_metrics/<point_name>/summary.
    Uses the \"run\" band when summaries are banded (multi-row).
    """
    try:
        with open_db(db_path, "r") as h5:
            g_trial = h5[key.path()]
            g_pt = g_trial["ambulation_metrics"][point_name]
            summary = _summary_run_row(g_pt)
            if summary is None:
                return None
            exit_dtype = np.dtype([
                ("latency_to_exit_s", np.float64),
                ("time_in_exit_zone_s", np.float64),
                ("time_in_exit_zone_fraction", np.float64),
                ("mean_distance_to_exit_cm", np.float64),
                ("min_distance_to_exit_cm", np.float64),
                ("path_efficiency", np.float64),
                ("n_exit_zone_entries", np.int32),
            ])
            out = np.zeros((1,), dtype=exit_dtype)
            for name in out.dtype.names:
                out[name] = summary[name]
            return out
    except (KeyError, ValueError):
        return None


# Legacy dtype alias for readers that expect exit_metrics shape
def exit_metrics_dtype() -> np.dtype:
    """Structured dtype for exit metrics (subset of node summary)."""
    return np.dtype([
        ("latency_to_exit_s", np.float64),
        ("time_in_exit_zone_s", np.float64),
        ("time_in_exit_zone_fraction", np.float64),
        ("mean_distance_to_exit_cm", np.float64),
        ("min_distance_to_exit_cm", np.float64),
        ("path_efficiency", np.float64),
        ("n_exit_zone_entries", np.int32),
    ])


def ambulation_summary_dtype() -> np.dtype:
    """Structured dtype for ambulation-only summary (subset of node summary)."""
    return np.dtype([
        ("total_distance_m", np.float64),
        ("mean_speed_mps", np.float64),
        ("max_speed_mps", np.float64),
        ("time_moving_s", np.float64),
        ("time_immobile_s", np.float64),
        ("n_movement_bouts", np.int32),
    ])


# =============================================================================
# QC Images
# =============================================================================

def write_qc_image(
    db_path: Optional[Path],
    key: TrialKey,
    name: str,
    image: np.ndarray,
    attrs: Optional[dict[str, Any]] = None,
) -> None:
    """
    Write a QC image to the database.
    
    Args:
        db_path: Path to database
        key: Trial key
        name: Image name (e.g., "trajectory", "dwell_heatmap")
        image: Image array (BGR or grayscale)
        attrs: Optional attributes to store with image
    """
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        g_qc = _ensure_group(g_trial, "qc_images")
        
        if name in g_qc:
            del g_qc[name]
        
        arr = np.asarray(image, dtype=np.uint8)
        store_format = (QC_IMAGE_STORE_FORMAT or "png_bytes").strip().lower()
        ds: h5py.Dataset
        if store_format == "png_bytes":
            try:
                import cv2  # local import: optional dependency

                ok, enc = cv2.imencode(".png", arr)
                if ok and enc is not None:
                    payload = np.asarray(enc, dtype=np.uint8)
                    ds = g_qc.create_dataset(name, data=payload, compression="gzip")
                    ds.attrs["CLASS"] = "IMAGE"
                    ds.attrs["ENCODING"] = "png"
                else:
                    ds = g_qc.create_dataset(name, data=arr, compression="gzip")
                    ds.attrs["CLASS"] = "IMAGE"
                    ds.attrs["ENCODING"] = "raw"
            except Exception:
                ds = g_qc.create_dataset(name, data=arr, compression="gzip")
                ds.attrs["CLASS"] = "IMAGE"
                ds.attrs["ENCODING"] = "raw"
        else:
            ds = g_qc.create_dataset(name, data=arr, compression="gzip")
            ds.attrs["CLASS"] = "IMAGE"
            ds.attrs["ENCODING"] = "raw"
        
        if attrs:
            for k, v in attrs.items():
                try:
                    ds.attrs[k] = v
                except Exception:
                    ds.attrs[k] = _safe_str(v)


def read_qc_image(
    db_path: Optional[Path],
    key: TrialKey,
    name: str,
) -> Optional[np.ndarray]:
    """Read a QC image from the database."""
    try:
        with open_db(db_path, "r") as h5:
            g_trial = h5[key.path()]
            ds = g_trial["qc_images"][name]
            enc = _safe_str(ds.attrs.get("ENCODING", "raw")).lower()
            data = ds[:]
            if enc == "png":
                try:
                    import cv2  # local import: optional dependency

                    decoded = cv2.imdecode(np.asarray(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                    if decoded is not None:
                        return decoded
                except Exception:
                    pass
            return data
    except (KeyError, ValueError):
        return None


# =============================================================================
# Animal Labels (Treatment Groups)
# =============================================================================


def write_animal_notes_attr(
    db_path: Optional[Path],
    animal_id: str,
    notes: str,
) -> None:
    """Set ``notes`` on the top-level ``/{animal_id}`` group (from treatment_labels CSV)."""
    with open_db(db_path, "a") as h5:
        if animal_id in h5:
            g_animal = h5[animal_id]
        else:
            g_animal = h5.create_group(animal_id)
        g_animal.attrs["notes"] = _safe_str(notes)


def upsert_trial_manifest_row(db_path: Optional[Path], manifest: "TrialManifest") -> None:
    """
    Append or replace one row in ``metadata/trial_manifest`` (columns match trial manifest CSV).
    """
    from ..io.file_discovery import MANIFEST_CSV_FIELDNAMES, trial_manifest_csv_row_values

    vals = trial_manifest_csv_row_values(manifest)
    # identity = (animal_id, session, trial); CSV column order has original_session at index 2
    row_key = (str(manifest.animal_id), str(manifest.session), str(manifest.trial))
    dt = np.dtype([(name, h5py.string_dtype(encoding="utf-8")) for name in MANIFEST_CSV_FIELDNAMES])

    def decode_cell(x: Any) -> str:
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="replace")
        if x is None:
            return ""
        return str(x)

    with open_db(db_path, "a") as h5:
        meta = _ensure_group(h5, "metadata")
        name = "trial_manifest"
        rows: list[tuple[str, ...]] = []
        if name in meta:
            old = meta[name][:]
            for i in range(old.shape[0]):
                t = tuple(decode_cell(old[i][fn]) for fn in MANIFEST_CSV_FIELDNAMES)
                rows.append(t)
            replaced = False
            for i, t in enumerate(rows):
                if (t[0], t[1], t[3]) == row_key:
                    rows[i] = tuple(str(v) for v in vals)
                    replaced = True
                    break
            if not replaced:
                rows.append(tuple(str(v) for v in vals))
        else:
            rows.append(tuple(str(v) for v in vals))
        new_arr = np.array(rows, dtype=dt)
        if name in meta:
            del meta[name]
        chunk = min(64, max(1, len(new_arr)))
        meta.create_dataset(name, data=new_arr, compression="gzip", chunks=(chunk,))


def write_trial_manifest_rows(
    db_path: Optional[Path],
    manifests: list["TrialManifest"],
) -> None:
    """
    Rewrite ``metadata/trial_manifest`` once from a list of manifests.
    Use this for init/sync to avoid costly per-trial dataset churn.
    """
    from ..io.file_discovery import MANIFEST_CSV_FIELDNAMES, trial_manifest_csv_row_values

    dt = np.dtype([(name, h5py.string_dtype(encoding="utf-8")) for name in MANIFEST_CSV_FIELDNAMES])
    rows = [tuple(str(v) for v in trial_manifest_csv_row_values(m)) for m in manifests]
    arr = np.array(rows, dtype=dt)
    with open_db(db_path, "a") as h5:
        meta = _ensure_group(h5, "metadata")
        name = "trial_manifest"
        if name in meta:
            del meta[name]
        chunk = min(256, max(1, len(arr)))
        meta.create_dataset(name, data=arr, compression="gzip", chunks=(chunk,))


def write_animal_label(
    db_path: Optional[Path],
    animal_id: str,
    sex: Optional[str] = None,
    tx: Optional[str] = None,
    strain: Optional[str] = None,
    experiment: Optional[str] = None,
    researcher: Optional[str] = None,
    drug: Optional[str] = None,
) -> None:
    """
    Write treatment labels for an animal.

    Args:
        db_path: Path to database
        animal_id: Animal ID
        sex: Sex (M/F)
        tx: Treatment group
        strain: Strain (e.g., F344-WT, F344t-AD, AZm -/-, AZm +/+)
        experiment: Experiment type (e.g., VAST_NP, LAST_NP, VASTcontKL)
        researcher: Researcher name (e.g., Nickolas Pasetto)
        drug: Drug condition (e.g., vehicle, compound name)
    """
    with open_db(db_path, "a") as h5:
        # Store on the animal group
        if animal_id in h5:
            g_animal = h5[animal_id]
        else:
            g_animal = h5.create_group(animal_id)

        if sex is not None:
            g_animal.attrs["sex"] = _safe_str(sex)
        if tx is not None:
            g_animal.attrs["tx"] = _safe_str(tx)
        if strain is not None:
            g_animal.attrs["strain"] = _safe_str(strain)
        if experiment is not None:
            g_animal.attrs["experiment"] = _safe_str(experiment)
        if researcher is not None:
            g_animal.attrs["researcher"] = _safe_str(researcher)
        if drug is not None:
            g_animal.attrs["drug"] = _safe_str(drug)


def read_animal_label(
    db_path: Optional[Path],
    animal_id: str,
) -> dict[str, str]:
    """Read treatment labels for an animal."""
    try:
        with open_db(db_path, "r") as h5:
            if animal_id not in h5:
                return {}
            g_animal = h5[animal_id]
            return {
                "sex": _safe_str(g_animal.attrs.get("sex", "")),
                "tx": _safe_str(g_animal.attrs.get("tx", "")),
                "notes": _safe_str(g_animal.attrs.get("notes", "")),
                "strain": _safe_str(g_animal.attrs.get("strain", "")),
                "experiment": _safe_str(g_animal.attrs.get("experiment", "")),
                "researcher": _safe_str(g_animal.attrs.get("researcher", "")),
                "drug": _safe_str(g_animal.attrs.get("drug", "")),
            }
    except (KeyError, ValueError):
        return {}


# =============================================================================
# Utility Functions
# =============================================================================

def trial_has_settings(db_path: Optional[Path], key: TrialKey) -> bool:
    """Return True if the trial group exists and has settings (e.g. arena_radius_px or trial_start_frame)."""
    try:
        with open_db(db_path, "r") as h5:
            if key.animal_id not in h5:
                return False
            g_animal = h5[key.animal_id]
            if key.session not in g_animal:
                return False
            g_session = g_animal[key.session]
            if key.trial not in g_session:
                return False
            g_trial = g_session[key.trial]
            return "arena_radius_px" in g_trial.attrs or "trial_start_frame" in g_trial.attrs
    except (KeyError, ValueError):
        return False


def delete_trial_group(db_path: Optional[Path], key: TrialKey) -> None:
    """Delete a trial group from the database. Does not delete parent groups."""
    with open_db(db_path, "a") as h5:
        if key.animal_id not in h5:
            return
        g_animal = h5[key.animal_id]
        if key.session not in g_animal:
            return
        g_session = g_animal[key.session]
        if key.trial in g_session:
            del g_session[key.trial]


def delete_animal_group(db_path: Optional[Path], animal_id: str) -> None:
    """Delete the animal group from the database (e.g. after pruning all its trials)."""
    with open_db(db_path, "a") as h5:
        if animal_id in h5 and animal_id != "metadata":
            del h5[animal_id]


def list_trials(db_path: Optional[Path] = None) -> list[TrialKey]:
    """List all trials in the database. Layout: /animal_id/session/trial (no phase level)."""
    trials = []
    with open_db(db_path, "r") as h5:
        for animal_id in h5.keys():
            if animal_id == "metadata":
                continue
            g_animal = h5[animal_id]
            if not isinstance(g_animal, h5py.Group):
                continue
            for session in g_animal.keys():
                g_session = g_animal[session]
                if not isinstance(g_session, h5py.Group):
                    continue
                for trial in g_session.keys():
                    g_trial = g_session[trial]
                    if isinstance(g_trial, h5py.Group):
                        trials.append(TrialKey(
                            animal_id=animal_id,
                            session=session,
                            trial=trial,
                        ))
    return sorted(trials, key=lambda t: (t.animal_id, t.session, t.trial))


def write_config_params(
    db_path: Optional[Path],
    key: TrialKey,
) -> None:
    """Write pipeline configuration parameters to trial attributes."""
    from .. import config
    
    with open_db(db_path, "a") as h5:
        g_trial = h5[key.path()]
        
        # Movement thresholds
        g_trial.attrs["movement_start_threshold"] = float(config.MOVEMENT_START_THRESHOLD_M_PER_FRAME)
        g_trial.attrs["movement_stop_threshold"] = float(config.MOVEMENT_STOP_THRESHOLD_M_PER_FRAME)
        g_trial.attrs["movement_speed_median_window_frames"] = int(config.MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES)
        g_trial.attrs["movement_entry_debounce_frames"] = int(config.MOVEMENT_ENTRY_DEBOUNCE_FRAMES)
        g_trial.attrs["movement_exit_debounce_frames"] = int(config.MOVEMENT_EXIT_DEBOUNCE_FRAMES)
        g_trial.attrs["min_movement_bout_duration_s"] = float(config.MIN_MOVEMENT_BOUT_DURATION_S)
        
        # Trace processing
        g_trial.attrs["trace_max_gap_frames"] = int(config.TRACE_MAX_GAP_FRAMES)
        g_trial.attrs["trace_smoothing_window"] = int(config.TRACE_SMOOTHING_WINDOW)
        
        # Exit zone
        g_trial.attrs["exit_zone_radius_cm"] = float(config.EXIT_ZONE_RADIUS_CM)
        
        # Pipeline version
        g_trial.attrs["pipeline_version"] = config.PIPELINE_VERSION
