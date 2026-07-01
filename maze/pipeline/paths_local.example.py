"""
Per-machine overrides for maze.pipeline.paths.

Copy this file to ``paths_local.py`` in the same directory (gitignored) and edit
paths for your lab drives. ``paths.py`` imports ``paths_local`` after setting
portable repo-relative defaults.

Example::

    cp maze/pipeline/paths_local.example.py maze/pipeline/paths_local.py
"""

from __future__ import annotations

from pathlib import Path

# Primary discovery root(s) for trial video/SLEAP discovery.
DATA_DIR = Path(r"D:\work sack\vibration maze")
DATA_DIRS: list[Path] = [DATA_DIR]

# Remap stored trial video_path prefixes when files moved to another drive.
# First element is the prefix stored in legacy H5 attrs; second is the local root.
VIDEO_PATH_PREFIX_REMAPS: list[tuple[str, str]] = [
    (
        r"E:\videos\vibration maze",
        r"C:\Users\admin\Documents\work\sack\datas\videos\vibration maze",
    ),
]

# Optional: override consolidated pipeline HDF5 output location.
# OUTPUT_H5 = Path(r"E:\analysis\maze_results.h5")

# Optional: discovery profile tweaks (uncomment to customize).
# from maze.pipeline.discovery_profiles import DiscoveryProfile
# DISCOVERY_PROFILE = DiscoveryProfile(
#     max_trial_num=9,
#     max_session_num=5,
#     session_renumber={"556": -1, "557": -1, "558": -1, "559": -1},
# )
