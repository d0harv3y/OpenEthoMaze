"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.fix_ele_h5_session_animal_ids import main

if __name__ == "__main__":
    raise SystemExit(main())
