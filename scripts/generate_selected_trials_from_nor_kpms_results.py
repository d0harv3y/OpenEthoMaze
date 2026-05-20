"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.generate_selected_trials_from_nor_kpms_results import main

if __name__ == "__main__":
    raise SystemExit(main())
