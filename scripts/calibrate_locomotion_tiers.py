"""Backward-compatible launcher. Prefer `uv run maze-calibrate-locomotion-tiers`."""
from maze.cli.calibrate_locomotion_tiers import main

if __name__ == "__main__":
    raise SystemExit(main())
