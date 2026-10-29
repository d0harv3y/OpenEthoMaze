"""Backward-compatible launcher. Prefer `uv run maze-of-floor-quad`."""

from maze.cli.of_floor_quad import main

if __name__ == "__main__":
    raise SystemExit(main())
