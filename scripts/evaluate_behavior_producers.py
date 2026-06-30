"""Backward-compatible launcher. Prefer `uv run maze-evaluate-behavior-producers`."""
from maze.cli.evaluate_behavior_producers import main

if __name__ == "__main__":
    raise SystemExit(main())
