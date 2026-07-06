"""Backward-compatible launcher. Prefer `uv run maze-init-behavior-token-labels`."""
from maze.cli.init_behavior_token_labels import main

if __name__ == "__main__":
    raise SystemExit(main())
