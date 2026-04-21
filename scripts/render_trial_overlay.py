"""
Render unified trial overlay video (manifest + pipeline HDF5 + optional kpMS).

Session strings must match the manifest CSV exactly (e.g. ``S01`` not ``1``).

Example::

    uv run python scripts/render_trial_overlay.py ^
      --manifest-csv outputs/legacy/trial_manifest_legacy.csv ^
      --pipeline-h5 outputs/legacy/vast_results_legacy.h5 ^
      --animal-id 1 --session S01 --trial T01 ^
      --out outputs/overlays ^
      --kpms-h5 "D:/work sack/.../results_apply.h5"

Requires ``uv sync --extra kpms`` for the hypnogram and exemplar tray.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from maze.pipeline.viz.overlay_cli import main_cli

_DEFAULT_MANIFEST = _PROJECT_ROOT / "outputs" / "legacy" / "trial_manifest_legacy.csv"
_DEFAULT_PIPELINE = _PROJECT_ROOT / "outputs" / "legacy" / "vast_results_legacy.h5"


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
