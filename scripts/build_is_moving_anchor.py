"""Backward-compatible launcher. Prefer `uv run maze-build-is-moving-anchor`."""
from maze.cli.build_is_moving_anchor import main

if __name__ == "__main__":
    raise SystemExit(main())
