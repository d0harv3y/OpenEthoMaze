"""Backward-compatible launcher. Prefer `uv run` console script (see readme.md)."""
from maze.cli.sleap_nn_batch_inference import main

if __name__ == "__main__":
    raise SystemExit(main())
