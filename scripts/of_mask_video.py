"""Backward-compatible launcher. Prefer `uv run maze-of-mask-video`."""

from maze.cli.of_mask_video import main

if __name__ == "__main__":
    raise SystemExit(main())
