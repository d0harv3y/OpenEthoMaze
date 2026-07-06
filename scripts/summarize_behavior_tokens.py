"""Backward-compatible launcher. Prefer `uv run maze-summarize-behavior-tokens`."""
from maze.cli.summarize_behavior_tokens import main

if __name__ == "__main__":
    raise SystemExit(main())
