"""Backward-compatible launcher. Prefer `uv run maze-join-stimulus-bouts`."""
from maze.cli.join_stimulus_bouts import main

if __name__ == "__main__":
    raise SystemExit(main())
