"""Backward-compatible launcher. Prefer `uv run maze-block-ethogram-exports`."""
from maze.cli.block_ethogram_exports import main

if __name__ == "__main__":
    raise SystemExit(main())
