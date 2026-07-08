"""Backward-compatible launcher. Prefer `uv run maze-compute-stimulus-mi`."""
from maze.cli.compute_stimulus_mi import main

if __name__ == "__main__":
    raise SystemExit(main())
