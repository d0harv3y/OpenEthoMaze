"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.legacy_db import main

if __name__ == "__main__":
    raise SystemExit(main())
