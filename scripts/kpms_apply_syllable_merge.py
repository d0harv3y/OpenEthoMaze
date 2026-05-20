"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.kpms_apply_syllable_merge import main

if __name__ == "__main__":
    raise SystemExit(main())
