"""
WSL2 path overrides for maze.pipeline.paths.

Copy to ``paths_local.py`` **inside WSL** (gitignored) when running kpMS fit from
Linux against Windows-mounted drives.

Example::

    cp maze/pipeline/paths_local.wsl.example.py maze/pipeline/paths_local.py

See docs/wsl_kpms_setup.md and docs/phase_wsl_agent_prompt.md.
"""

from __future__ import annotations

from pathlib import Path

# Primary discovery root(s) — Windows D: as /mnt/d/ in WSL.
DATA_DIR = Path("/mnt/d/scratch/vibration maze")
DATA_DIRS: list[Path] = [DATA_DIR]

# Optional consolidated pipeline HDF5 (same mount translation).
# OUTPUT_H5 = Path("/mnt/d/analysis/maze_results.h5")
