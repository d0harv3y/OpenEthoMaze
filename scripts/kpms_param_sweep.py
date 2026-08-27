"""Shim: uv run maze-kpms-param-sweep (see maze.cli.kpms_param_sweep)."""
from maze.cli.kpms_param_sweep import main

if __name__ == "__main__":
    raise SystemExit(main())
