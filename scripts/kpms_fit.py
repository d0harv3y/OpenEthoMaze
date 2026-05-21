"""Backward-compatible launcher. Prefer ``uv run maze-kpms-fit`` (requires ``--extra kpms``)."""
from maze.kpms.fit import main

if __name__ == "__main__":
    raise SystemExit(main())
