"""Shim: ``uv run maze-export-bout-arhmm-labeling``."""
from maze.cli.export_bout_arhmm_labeling import main

if __name__ == "__main__":
    raise SystemExit(main())
