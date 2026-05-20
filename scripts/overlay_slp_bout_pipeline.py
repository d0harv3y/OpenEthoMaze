"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.overlay_slp_bout_pipeline import main

if __name__ == "__main__":
    raise SystemExit(main())
