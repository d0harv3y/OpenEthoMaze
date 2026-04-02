from __future__ import annotations

from ..core.tasks import ARENA_TYPE_CIRCULAR, ARENA_TYPE_RADIAL_ARM
from .io.file_discovery import TrialManifest
from .mistrial_detection import detect_mistrial


def expected_frame_diff(arena_type: str) -> int | None:
    """Return the expected ``video_n_frames - h5_n_frames`` for a task, if enforced."""
    if arena_type == ARENA_TYPE_CIRCULAR:
        return -1
    return None


def trial_matches_frame_policy(manifest: TrialManifest, arena_type: str) -> bool:
    """Return whether a trial satisfies the task-specific frame-count policy."""
    diff = expected_frame_diff(arena_type)
    if diff is None:
        return True
    if manifest.h5_n_frames is None or manifest.video_n_frames is None:
        return False
    return (manifest.video_n_frames - manifest.h5_n_frames) == diff


def detect_task_mistrial(manifest: TrialManifest, arena_type: str) -> str | None:
    """Task-specific mistrial hook with explicit dispatch seams per task."""
    if arena_type == ARENA_TYPE_RADIAL_ARM:
        return detect_mistrial(manifest)
    return detect_mistrial(manifest)
