"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.export_ram_trial_manifest_csv import main

if __name__ == "__main__":
    raise SystemExit(main())
