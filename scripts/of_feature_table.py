""" Backward-compatible launcher. Prefer `uv run maze-of-feature-table`."""

from maze.cli.of_feature_table import main

if __name__ == "__main__":
    raise SystemExit(main())
