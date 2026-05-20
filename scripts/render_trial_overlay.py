"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.render_trial_overlay import main

if __name__ == "__main__":
    raise SystemExit(main())
