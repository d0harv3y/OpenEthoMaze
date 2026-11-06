""" Backward-compatible launcher. Prefer `uv run maze-of-overlay-metrics`."""

from maze.cli.of_overlay_metrics import main

if __name__ == "__main__":
    raise SystemExit(main())
