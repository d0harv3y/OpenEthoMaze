"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.build_kpms_training_exemplar_table import main

if __name__ == "__main__":
    raise SystemExit(main())
