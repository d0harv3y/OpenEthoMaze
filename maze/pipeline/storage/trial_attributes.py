from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from maze.core.schema import TASK_DATA_GROUP
from maze.core.storage import ensure_task_group, write_group_attrs
from maze.core.tasks import normalize_arena_type

from ._shared import open_db, safe_str
from .trial_key import TrialKey


def write_trial_attrs(
    db_path: Optional[Path],
    key: TrialKey,
    attrs: dict[str, Any],
) -> None:
    """Persist extra task-specific attributes on a trial group."""
    if db_path is None or not attrs:
        return
    with open_db(db_path, "a") as h5:
        write_group_attrs(h5[key.path()], attrs)


def write_task_group_attrs(
    db_path: Optional[Path],
    key: TrialKey,
    task_name: str,
    attrs: dict[str, Any],
) -> None:
    """Persist task-specific attrs under ``task_data/<task_name>`` for a trial."""
    if db_path is None or not attrs:
        return
    with open_db(db_path, "a") as h5:
        g_task = ensure_task_group(h5[key.path()], task_name)
        write_group_attrs(g_task, attrs)


def read_task_group_attrs(
    db_path: Optional[Path],
    key: TrialKey,
    task_name: str,
) -> dict[str, Any]:
    """Read task-specific attrs from ``task_data/<task_name>`` for a trial."""
    try:
        with open_db(db_path, "r") as h5:
            g_task_root = h5[key.path()].get(TASK_DATA_GROUP)
            if g_task_root is None:
                return {}
            g_task = g_task_root.get(normalize_arena_type(task_name))
            if g_task is None:
                return {}
            return {name: g_task.attrs[name] for name in g_task.attrs.keys()}
    except (KeyError, ValueError):
        return {}


def write_trial_frame_counts(
    db_path: Optional[Path],
    key: TrialKey,
    h5_n_frames: int,
    video_n_frames: int,
) -> None:
    """Write H5 and video frame counts for frame-diff filtering."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        write_group_attrs(
            h5[key.path()],
            {"h5_n_frames": int(h5_n_frames), "video_n_frames": int(video_n_frames)},
        )


def write_video_meta(
    db_path: Optional[Path],
    key: TrialKey,
    fps: float,
    n_frames: int,
    duration_s: float,
) -> None:
    """Write video metadata to trial attributes."""
    with open_db(db_path, "a") as h5:
        write_group_attrs(
            h5[key.path()],
            {"fps": float(fps), "n_frames": int(n_frames), "duration_s": float(duration_s)},
        )


def write_analysis_duration(
    db_path: Optional[Path],
    key: TrialKey,
    analysis_duration_s: float,
) -> None:
    """Write analysis-window duration (excludes ITI) for reporting."""
    with open_db(db_path, "a") as h5:
        write_group_attrs(
            h5[key.path()], {"analysis_duration_s": float(analysis_duration_s)}
        )


def write_primary_trajectory(
    db_path: Optional[Path],
    key: TrialKey,
    primary_trajectory: str,
) -> None:
    """Write which trajectory is primary for export."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        write_group_attrs(
            h5[key.path()], {"primary_trajectory": safe_str(primary_trajectory)}
        )


def write_mistrial_reason(
    db_path: Optional[Path],
    key: TrialKey,
    reason: str,
) -> None:
    """Write mistrial reason to trial attributes."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        write_group_attrs(h5[key.path()], {"mistrial_reason": safe_str(reason)})


def write_sleap_path(
    db_path: Optional[Path],
    key: TrialKey,
    sleap_path: str,
) -> None:
    """Write the path to the SLEAP predictions file to trial attrs."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        write_group_attrs(h5[key.path()], {"sleap_path": safe_str(sleap_path)})


def write_sleap_model_path(
    db_path: Optional[Path],
    key: TrialKey,
    model_path: str,
) -> None:
    """Write the SLEAP model path used for inference to trial attrs."""
    if db_path is None:
        return
    with open_db(db_path, "a") as h5:
        write_group_attrs(
            h5[key.path()], {"sleap_model_path": safe_str(model_path)}
        )


def write_animal_notes_attr(
    db_path: Optional[Path],
    animal_id: str,
    notes: str,
) -> None:
    """Set ``notes`` on the top-level ``/{animal_id}`` group."""
    with open_db(db_path, "a") as h5:
        g_animal = h5[animal_id] if animal_id in h5 else h5.create_group(animal_id)
        write_group_attrs(g_animal, {"notes": safe_str(notes)})


def write_config_params(
    db_path: Optional[Path],
    key: TrialKey,
) -> None:
    """Write pipeline configuration parameters to trial attributes."""
    from .. import defaults

    with open_db(db_path, "a") as h5:
        write_group_attrs(
            h5[key.path()],
            {
                "movement_start_threshold": float(
                    defaults.MOVEMENT_START_THRESHOLD_M_PER_FRAME
                ),
                "movement_stop_threshold": float(
                    defaults.MOVEMENT_STOP_THRESHOLD_M_PER_FRAME
                ),
                "movement_speed_median_window_frames": int(
                    defaults.MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES
                ),
                "movement_entry_debounce_frames": int(
                    defaults.MOVEMENT_ENTRY_DEBOUNCE_FRAMES
                ),
                "movement_exit_debounce_frames": int(
                    defaults.MOVEMENT_EXIT_DEBOUNCE_FRAMES
                ),
                "min_movement_bout_duration_s": float(
                    defaults.MIN_MOVEMENT_BOUT_DURATION_S
                ),
                "trace_max_gap_frames": int(defaults.TRACE_MAX_GAP_FRAMES),
                "trace_smoothing_window": int(defaults.TRACE_SMOOTHING_WINDOW),
                "exit_zone_radius_cm": float(defaults.EXIT_ZONE_RADIUS_CM),
                "pipeline_version": defaults.PIPELINE_VERSION,
            },
        )
