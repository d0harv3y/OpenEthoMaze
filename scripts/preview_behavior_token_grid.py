"""Backward-compatible launcher. Prefer `uv run maze-preview-behavior-token-grid`."""
from maze.cli.preview_behavior_token_grid import main

if __name__ == "__main__":
    raise SystemExit(main())
