"""Configuration surface for the maze pipeline.

Algorithm defaults live in ``defaults.py`` while local machine paths stay here
so they can be overridden in ``config_local.py`` without editing shared values.
"""

from __future__ import annotations

from pathlib import Path

from ..core.anatomy import (
    FALLBACK_NODE_INDEX,
    SKELETON_EDGES,
    SPOT_NODE_NAMES,
    STANDARD_NODE_NAMES,
)
from .defaults import *
from .discovery_profiles import DEFAULT_DISCOVERY_PROFILE, DiscoveryProfile

# Multiple roots for discovery; keep these repo-relative by default and override
# them locally when working against real data volumes.
DATA_DIR = DEFAULT_DATA_DIR
DATA_DIRS: list[Path] = [DATA_DIR]
OUTPUT_H5 = DEFAULT_OUTPUT_H5

# Point names for ambulation/exit metrics:
# - spot: front-body mean (SLEAP-only)
# - centroid: all SLEAP nodes mean
# - in-range: controller/legacy fallback
# - spot_hybrid: SLEAP spot with long gaps replaced by in-range when available
IN_RANGE_POINT_NAME = "in-range"
HYBRID_POINT_NAME = "spot_hybrid"
AMBIULATION_POINT_NAMES = ("spot", "centroid", "in-range", HYBRID_POINT_NAME)

DISCOVERY_PROFILE: DiscoveryProfile = DEFAULT_DISCOVERY_PROFILE
MAX_TRIAL_NUM = DISCOVERY_PROFILE.max_trial_num
MAX_SESSION_NUM = DISCOVERY_PROFILE.max_session_num
SESSION_RENUMBER = dict(DISCOVERY_PROFILE.session_renumber)


def get_config_snapshot() -> dict:
    """Return a dictionary of current configuration values for reproducibility."""
    return {
        "pipeline_version": PIPELINE_VERSION,
        "default_fps": DEFAULT_FPS,
        "epoch_length_s": EPOCH_LENGTH_S,
        "exit_zone_radius_cm": EXIT_ZONE_RADIUS_CM,
        "movement_start_threshold": MOVEMENT_START_THRESHOLD_M_PER_FRAME,
        "movement_stop_threshold": MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
        "movement_speed_median_window_frames": MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES,
        "movement_entry_debounce_frames": MOVEMENT_ENTRY_DEBOUNCE_FRAMES,
        "movement_exit_debounce_frames": MOVEMENT_EXIT_DEBOUNCE_FRAMES,
        "min_movement_bout_duration_s": MIN_MOVEMENT_BOUT_DURATION_S,
        "trace_max_gap_frames": TRACE_MAX_GAP_FRAMES,
        "trace_smoothing_window": TRACE_SMOOTHING_WINDOW,
        "min_confident_nodes_per_frame": MIN_CONFIDENT_NODES_PER_FRAME,
        "min_node_confidence_threshold": MIN_NODE_CONFIDENCE_THRESHOLD,
        "min_mean_confidence_per_frame": MIN_MEAN_CONFIDENCE_PER_FRAME,
    }

try:
    from .config_local import *
except ImportError:
    pass