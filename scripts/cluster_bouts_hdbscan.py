"""Backward-compatible launcher. Prefer `uv run maze-cluster-bouts-hdbscan`."""
from maze.cli.cluster_bouts_hdbscan import main

if __name__ == "__main__":
    raise SystemExit(main())
