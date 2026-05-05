"""Visualization and QC module."""

from __future__ import annotations

from typing import Any

__all__ = [
    "generate_trial_qc_images",
    "render_overlay_video",
]


def __getattr__(name: str) -> Any:
    if name == "generate_trial_qc_images":
        from .qc_images import generate_trial_qc_images

        return generate_trial_qc_images
    if name == "render_overlay_video":
        from .video_overlay import render_overlay_video

        return render_overlay_video
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted({*globals().keys(), *__all__})
