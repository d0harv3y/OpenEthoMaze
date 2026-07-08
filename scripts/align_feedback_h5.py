"""Backward-compatible launcher. Prefer `uv run maze-align-feedback-h5`."""
from maze.cli.align_feedback_h5 import main

if __name__ == "__main__":
    raise SystemExit(main())
