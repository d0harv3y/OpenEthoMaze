"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.reprocess_controller_h5 import main

if __name__ == "__main__":
    raise SystemExit(main())
