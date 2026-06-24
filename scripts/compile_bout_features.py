"""Backward-compatible launcher. Prefer `uv run maze-compile-bout-features`."""
from maze.cli.compile_bout_features import main

if __name__ == "__main__":
    raise SystemExit(main())
