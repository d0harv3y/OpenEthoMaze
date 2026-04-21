"""
Render unified trial overlay for radial-arm maze (RAM) ORM trials.

Uses the same pipeline as ``render_trial_overlay.py`` but defaults the manifest to
``inputs/ram_trial_manifest.csv`` (from ``export_ram_trial_manifest_csv.py``).
You must pass ``--pipeline-h5`` to your RAM ORM HDF5 (``task_data/radial_arm`` for template geometry).

Example::

    uv run python scripts/export_ram_trial_manifest_csv.py --video-base "D:/data/videos" ^
      --trial-ns ORM/inputs/trial_ns.csv --pipeline-h5 path/to/ram_pipeline.h5 ^
      --out-csv ORM/inputs/ram_trial_manifest.csv

    uv run python scripts/render_ram_trial_overlay.py ^
      --manifest-csv ORM/inputs/ram_trial_manifest.csv ^
      --pipeline-h5 path/to/ram_pipeline.h5 ^
      --animal-id 1 --session train-1 --trial T01 ^
      --out outputs/overlays
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from maze.pipeline.viz.overlay_cli import main_cli  # noqa: E402

_DEFAULT_MANIFEST = _PROJECT_ROOT / "inputs" / "ram_trial_manifest.csv"


def main() -> int:
    return main_cli(
        manifest_default=_DEFAULT_MANIFEST,
        pipeline_default=None,
        description=(
            "Unified ORM overlay for radial-arm maze: source video + RAM pipeline HDF5 "
            "(template arms/center/hole from task_data/radial_arm) + optional kpMS."
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
