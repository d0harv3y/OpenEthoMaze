"""Backward-compatible launcher. Prefer `uv run maze-average-block-dwell-plots`."""
from maze.cli.average_block_dwell_plots import main

if __name__ == "__main__":
    raise SystemExit(main())
