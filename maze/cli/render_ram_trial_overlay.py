"""
Render unified trial overlay for radial-arm maze (RAM) ORM trials.

Uses the same pipeline as ``render_trial_overlay.py`` but defaults the manifest to
``inputs/ram_trial_manifest.csv`` (from ``export_ram_trial_manifest_csv.py``).
You must pass ``--pipeline-h5`` to your RAM ORM HDF5 (``task_data/radial_arm`` for template geometry).

Example::

    uv run maze-export-ram-trial-manifest --video-base "D:/data/videos" ^
      --trial-ns inputs/trial_ns.csv --pipeline-h5 path/to/ram_pipeline.h5 ^
      --out-csv inputs/ram_trial_manifest.csv

    uv run maze-render-ram-trial-overlay ^
      --manifest-csv inputs/ram_trial_manifest.csv ^
      --pipeline-h5 path/to/ram_pipeline.h5 ^
      --animal-id 1 --session train-1 --trial T01 ^
      --out outputs/overlays
"""

from __future__ import annotations


from maze.pipeline.viz.overlay_cli import main_cli
from maze.repo_paths import REPO_ROOT

_DEFAULT_MANIFEST = REPO_ROOT / "inputs" / "ram_trial_manifest.csv"


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
