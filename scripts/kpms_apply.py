"""Backward-compatible launcher. Prefer ``uv run maze-kpms-apply`` (requires ``--extra kpms``)."""
from maze.kpms.apply import main

if __name__ == "__main__":
    raise SystemExit(main())
