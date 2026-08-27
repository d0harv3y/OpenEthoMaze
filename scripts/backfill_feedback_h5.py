"""Backward-compatible launcher. Prefer `uv run maze-backfill-feedback-h5`."""
from maze.cli.backfill_feedback_h5 import main

if __name__ == "__main__":
    raise SystemExit(main())
