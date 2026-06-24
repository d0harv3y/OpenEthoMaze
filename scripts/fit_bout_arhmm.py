"""Backward-compatible launcher. Prefer `uv run maze-fit-bout-arhmm`."""
from maze.cli.fit_bout_arhmm import main

if __name__ == "__main__":
    raise SystemExit(main())
