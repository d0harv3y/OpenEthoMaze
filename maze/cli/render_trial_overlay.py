"""
Render unified trial overlay video (manifest + pipeline HDF5 + optional kpMS).

Session strings must match the manifest CSV exactly (e.g. ``S01`` not ``1``).

Example::

    uv run maze-render-trial-overlay ^
      --manifest-csv outputs/legacy/trial_manifest_legacy.csv ^
      --pipeline-h5 outputs/legacy/vast_results_legacy.h5 ^
      --animal-id 1 --session S01 --trial T01 ^
      --out outputs/overlays ^
      --kpms-h5 /path/to/results_apply.h5

Requires ``uv sync --extra kpms`` for the hypnogram and exemplar tray.
"""

from __future__ import annotations


from maze.pipeline.viz.overlay_cli import main_cli
from maze.repo_paths import REPO_ROOT

_DEFAULT_MANIFEST = REPO_ROOT / "outputs" / "legacy" / "trial_manifest_legacy.csv"
_DEFAULT_PIPELINE = REPO_ROOT / "outputs" / "legacy" / "vast_results_legacy.h5"


def main() -> int:
    return main_cli(
        manifest_default=_DEFAULT_MANIFEST,
        pipeline_default=_DEFAULT_PIPELINE,
        description=(
            "Unified ORM overlay: source video + pipeline HDF5 + optional kpMS hypnogram "
            "and exemplar tray."
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
