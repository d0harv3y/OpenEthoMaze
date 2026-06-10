"""kpMS project directory layout per pose stream."""

from __future__ import annotations

from pathlib import Path

from .heading_idxs import PoseStream

POSE_STREAM_CHOICES: tuple[PoseStream, ...] = ("anatomical", "blob", "fused")


def default_kpms_root(output_dir: Path | str) -> Path:
    """Return ``<output_dir>/kpms`` (parent of per-stream project dirs)."""
    return Path(output_dir) / "kpms"


def resolve_kpms_project_dir(project_dir: Path | str, pose_stream: PoseStream) -> Path:
    """
    Resolve the stream-specific kpMS project directory.

    Layout: ``<kpms_root>/<pose_stream>/`` (model outputs live in
    ``<kpms_root>/<pose_stream>/<model_name>/``).
    """
    root = Path(project_dir)
    if root.name in POSE_STREAM_CHOICES:
        return root
    return root / pose_stream
