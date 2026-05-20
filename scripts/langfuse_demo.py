"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.langfuse_demo import main

if __name__ == "__main__":
    raise SystemExit(main())
