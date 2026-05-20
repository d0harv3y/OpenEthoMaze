"""Repository root paths for CLIs (installed package; no sys.path hacks)."""

from __future__ import annotations

from pathlib import Path

# maze/repo_paths.py -> parents[0] == maze/, parents[1] == OpenEthoMaze/
REPO_ROOT = Path(__file__).resolve().parents[1]
