from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Per-frame XY row (controller-side recording, px units only)
# ---------------------------------------------------------------------------

XY_ROW_DTYPE = np.dtype(
    [
        ("frame_index", np.uint32),
        ("t_s", np.float64),
        ("x", np.float32),
        ("y", np.float32),
        ("dist_to_exit_px", np.float32),
        ("trial_state", "S16"),
        ("in_exit_zone", np.uint8),
        ("valid", np.uint8),
        ("is_moving", np.uint8),
    ]
)


# ---------------------------------------------------------------------------
# Unified per-frame feedback row
# ---------------------------------------------------------------------------

FEEDBACK_ROW_DTYPE = np.dtype(
    [
        ("frame_index", np.uint32),
        ("trial_state", "S16"),
        ("motor_fb", np.float32),
        ("light_fb", np.float32),
        ("sound_fb", np.float32),
    ]
)


# ---------------------------------------------------------------------------
# Banded node summary (pipeline-side, per tracking point and trial_state band)
# ---------------------------------------------------------------------------

NODE_SUMMARY_DTYPE = np.dtype(
    [
        # Ambulation
        ("total_distance_m", np.float64),
        ("mean_speed_mps", np.float64),
        ("max_speed_mps", np.float64),
        ("time_moving_s", np.float64),
        ("time_immobile_s", np.float64),
        ("n_movement_bouts", np.int32),
        # Exit
        ("latency_to_exit_s", np.float64),
        ("time_in_exit_zone_s", np.float64),
        ("time_in_exit_zone_fraction", np.float64),
        ("mean_distance_to_exit_cm", np.float64),
        ("min_distance_to_exit_cm", np.float64),
        ("path_efficiency", np.float64),
        ("n_exit_zone_entries", np.int32),
        # Center
        ("time_in_center_s", np.float64),
        ("time_in_center_fraction", np.float64),
        ("n_center_entries", np.int32),
    ]
)


def node_summary_by_state_dtype() -> np.dtype:
    """Structured dtype for per-node summary split by trial_state band."""
    fields: list[tuple[str, object]] = [("trial_state", "S16")]
    fields.extend((name, NODE_SUMMARY_DTYPE.fields[name][0]) for name in NODE_SUMMARY_DTYPE.names)
    return np.dtype(fields)


NODE_SUMMARY_BY_STATE_DTYPE = node_summary_by_state_dtype()


# ---------------------------------------------------------------------------
# Common HDF5 group / dataset names
# ---------------------------------------------------------------------------

FEEDBACK_GROUP = "feedback"
FEEDBACK_TABLE_DATASET = "table"

AMBULATION_GROUP = "ambulation_metrics"
XY_DATASET_NAME = "xy"

