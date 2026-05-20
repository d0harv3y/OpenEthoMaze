"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.kpms_clean_syllable_bouts import main

if __name__ == "__main__":
    raise SystemExit(main())
