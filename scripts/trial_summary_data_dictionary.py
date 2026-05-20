"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.trial_summary_data_dictionary import main

if __name__ == "__main__":
    raise SystemExit(main())
