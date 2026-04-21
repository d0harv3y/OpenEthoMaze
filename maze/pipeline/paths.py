"""Local-machine and dataset-location settings for the maze pipeline."""

from __future__ import annotations

from pathlib import Path

from .discovery_profiles import DEFAULT_DISCOVERY_PROFILE, DiscoveryProfile

# DEFAULT_DATA_DIR = Path(r"D:\work sack\vibration maze")
DEFAULT_DATA_DIR = Path(r"E:\videos\vibration maze")
DEFAULT_OUTPUT_H5 = Path("outputs") / "maze_results.h5"

DATA_DIR = DEFAULT_DATA_DIR
DATA_DIRS: list[Path] = [DATA_DIR]
OUTPUT_H5 = DEFAULT_OUTPUT_H5

DISCOVERY_PROFILE: DiscoveryProfile = DEFAULT_DISCOVERY_PROFILE
MAX_TRIAL_NUM = DISCOVERY_PROFILE.max_trial_num
MAX_SESSION_NUM = DISCOVERY_PROFILE.max_session_num
SESSION_RENUMBER = dict(DISCOVERY_PROFILE.session_renumber)

MAX_WORKERS = 4
PARALLEL_ENABLED = True
PARALLEL_HDF5_WRITE = False

try:
    from .paths_local import *  # noqa: F403
except ImportError:
    try:
        from .config_local import *  # noqa: F403
    except ImportError:
        pass
