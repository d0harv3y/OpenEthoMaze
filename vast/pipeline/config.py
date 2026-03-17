"""
Configuration module for VAST Pipeline.

Single source of truth for all hardcoded parameters, paths, and settings.
Keep configuration in this file (not environment variables).
"""

from __future__ import annotations

import math
from pathlib import Path

# =============================================================================
# Pipeline metadata
# =============================================================================
PIPELINE_VERSION = "vast_v0.1"
PROCESSING_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# =============================================================================
# Paths
# =============================================================================
DATA_DIR = Path(r"D:\work sack\vibration maze")
# Multiple roots for discovery (add e.g. "az model female" to include another folder)
DATA_DIRS: list[Path] = [
    DATA_DIR,
    # Path(r"D:\work sack\vibration maze\az model female"),
]
OUTPUT_H5 = Path(r"C:\Users\admin\code\IMPRESS\VAST\vast_results.h5")

# =============================================================================
# Video / timing defaults
# =============================================================================
DEFAULT_FPS = 26.7  # Fallback FPS (median from H5 timer0; video metadata is wrong at 30)
EPOCH_LENGTH_S = 30.0  # Epoch bin duration (seconds) for temporal analyses

# =============================================================================
# Trial filtering (applied during discovery)
# =============================================================================
MAX_TRIAL_NUM = 9       # Exclude trials > T09 (e.g., T10)
MAX_SESSION_NUM = 5     # Exclude sessions > S05

# Cohort 5 session offset: these animals' sessions are numbered starting from 2
# in the source data. Shift all sessions down by 1 (S02->S01, S03->S02, etc.)
SESSION_RENUMBER: dict[str, int] = {
    "556": -1,
    "557": -1,
    "558": -1,
    "559": -1,
}

# =============================================================================
# Fixed node index mapping (parity with ehram/my_nor_wip)
# The SLEAP metadata node names are unreliable, so we use fixed indices.
# Node order must match the VAST SLEAP model output order. To verify: load a
# .slp, print metadata.nodes and compare to STANDARD_NODE_NAMES (see
# scripts/verify_sleap_nodes.py).
# =============================================================================
FALLBACK_NODE_INDEX = {
    "nose": 0,
    "tail": 1,
    "neck": 2,
    "hindL": 3,
    "foreL": 4,
    "foreR": 5,
    "hindR": 6,
    "spine": 7,
}

# Standard anatomical node order
STANDARD_NODE_NAMES = ["nose", "tail", "neck", "hindL", "foreL", "foreR", "hindR", "spine"]

# Nodes used for computing the "spot" (center-of-mass proxy)
SPOT_NODE_NAMES = ("nose", "neck", "foreL", "foreR") #, "spine"

# Point names for ambulation/exit metrics:
# - spot: front-body mean (SLEAP-only)
# - centroid: all SLEAP nodes mean
# - in-range: controller/legacy fallback
# - spot_hybrid: SLEAP spot with long gaps replaced by in-range when available
IN_RANGE_POINT_NAME = "in-range"
HYBRID_POINT_NAME = "spot_hybrid"
AMBIULATION_POINT_NAMES = ("spot", "centroid", "in-range", HYBRID_POINT_NAME)

# Skeleton edges for overlay (node name pairs; order matches STANDARD_NODE_NAMES)
SKELETON_EDGES: tuple[tuple[str, str], ...] = (
    ("nose", "neck"),
    ("neck", "spine"),
    ("spine", "tail"),
    ("tail", "hindL"),
    ("tail", "hindR"),
    ("neck", "foreL"),
    ("neck", "foreR"),
)

# =============================================================================
# Arena calibration
# =============================================================================
# Default pixels per cm (rough estimate, will be read from H5 settings per trial)
DEFAULT_PX_PER_CM = 2.42

# Exit zone definition
EXIT_ZONE_RADIUS_CM = 12.5  # Radius around exit position to consider "at exit"
QC_EXIT_ZONE_RADIUS_CM = 12.5  # Radius for drawing exit zone in QC composite (cm)

# Center zone (arena center) for center entries / time in center
# Use 70% of arena radius from trial (old H5 ROI); fallback when arena not available
CENTER_ZONE_RADIUS_FRACTION = 0.7  # Fraction of arena radius for center zone (e.g. 0.7 = 70%)
CENTER_ZONE_RADIUS_CM = 12.5  # Fallback radius (cm) when arena_radius not available
CENTER_ENTRY_DEBOUNCE_S = 0.5  # Min time outside center before re-entry counts (avoids overcounting)

# =============================================================================
# Movement bout parameters
# Thresholds are in meters per frame (matching ehram/my_nor_wip pattern)
# =============================================================================
MOVEMENT_START_THRESHOLD_M_PER_FRAME = math.sqrt(2) / 150  # ~2 pixels at typical resolution
MOVEMENT_STOP_THRESHOLD_M_PER_FRAME = math.sqrt(2) / 300   # ~1 pixel
MIN_MOVEMENT_BOUT_DURATION_S = 0.1  # Minimum bout duration in seconds
MOVEMENT_INTER_BOUT_INTERVAL_S = 0.166  # Merge bouts separated by <= this interval

# =============================================================================
# Frame-level filtering (discard frames with no animal present)
# Strategy: we reject by INDIVIDUAL NODES, not by frame-average confidence.
# - Per frame: count how many nodes have confidence >= MIN_NODE_CONFIDENCE_THRESHOLD.
#   Keep frame only if count >= MIN_CONFIDENT_NODES_PER_FRAME (and in a run of
#   MIN_VALID_FRAME_RUN_LENGTH). Optionally also require mean(node confidences) >=
#   MIN_MEAN_CONFIDENCE_PER_FRAME (when set) for noisier / out-of-domain model data.
# - Per-node: in trace processing, nodes with score < TRACE_CONFIDENCE_THRESHOLD
#   are treated as NaN and interpolated. So low-conf points are filled, not dropped.
# =============================================================================
FILTER_FRAMES_NO_ANIMAL = True
MIN_CONFIDENT_NODES_PER_FRAME = 3  # Require >= N nodes with confidence >= threshold
MIN_NODE_CONFIDENCE_THRESHOLD = 0.55  # Confidence threshold for nodes
MIN_VALID_FRAME_RUN_LENGTH = 5  # Minimum consecutive valid frames
# Optional: reject frame if mean(all node confidences) < this (None = disabled).
# Use e.g. 0.25–0.4 for noisier / out-of-domain SLEAP model output.
MIN_MEAN_CONFIDENCE_PER_FRAME: float | None = None

# =============================================================================
# Mistrial detection (before interpolation)
# =============================================================================
DETECT_MISTRIAL_BEFORE_PROCESSING = True
MIN_VALID_FRAME_FRACTION = 0.05  # Minimum fraction of frames that must be valid
MIN_VALID_FRAME_RUN_FOR_MISTRIAL = 15  # Minimum consecutive valid frames to avoid mistrial
MIN_TOTAL_MOVEMENT_PX_FOR_MISTRIAL = 42.0  # Minimum total displacement (px)

# =============================================================================
# Tracking data noise filtering
# =============================================================================
MAX_MOVEMENT_PER_FRAME_CM = 15.0  # Maximum movement between frames (cm)
JUMP_FILTER_LOOKAHEAD_FRAMES = 3  # Frames to check when confirming a large jump

# =============================================================================
# Trace processing parameters
# =============================================================================
TRACE_INTERPOLATE_NANS = True
TRACE_MAX_GAP_FRAMES = 15  # Maximum gap size to interpolate (frames)
TRACE_INTERPOLATE_LOW_CONF = True
TRACE_CONFIDENCE_THRESHOLD = 0.55
TRACE_APPLY_SMOOTHING = True
TRACE_SMOOTHING_WINDOW = 3  # Smoothing window size (frames)

# =============================================================================
# QC visualization
# =============================================================================
MAX_DWELL_TIME_S = 4.0  # Maximum dwell time for heatmap normalization
DWELL_HEATMAP_BLUR_SIGMA = 4.0  # Gaussian blur sigma for dwell-time heatmap

# =============================================================================
# Parallelization settings
# =============================================================================
MAX_WORKERS = 4
PARALLEL_ENABLED = True
PARALLEL_HDF5_WRITE = False  # Disable parallel HDF5 writes (causes file locking issues)

# =============================================================================
# Animal treatment labels (to be populated later)
# Structure: {animal_id: {'cohort': str, 'sex': str, 'tx': str}}
# =============================================================================
ANIMAL_INFO: dict[str, dict[str, str]] = {}


def get_config_snapshot() -> dict:
    """Return a dictionary of current configuration values for reproducibility."""
    return {
        "pipeline_version": PIPELINE_VERSION,
        "default_fps": DEFAULT_FPS,
        "epoch_length_s": EPOCH_LENGTH_S,
        "exit_zone_radius_cm": EXIT_ZONE_RADIUS_CM,
        "movement_start_threshold": MOVEMENT_START_THRESHOLD_M_PER_FRAME,
        "movement_stop_threshold": MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
        "min_movement_bout_duration_s": MIN_MOVEMENT_BOUT_DURATION_S,
        "trace_max_gap_frames": TRACE_MAX_GAP_FRAMES,
        "trace_smoothing_window": TRACE_SMOOTHING_WINDOW,
        "min_confident_nodes_per_frame": MIN_CONFIDENT_NODES_PER_FRAME,
        "min_node_confidence_threshold": MIN_NODE_CONFIDENCE_THRESHOLD,
        "min_mean_confidence_per_frame": MIN_MEAN_CONFIDENCE_PER_FRAME,
    }
