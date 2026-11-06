""" Backward-compatible launcher. Prefer `uv run maze-of-overlay-pose`."""

from maze.cli.of_overlay_pose import main

if __name__ == "__main__":
    raise SystemExit(main())
