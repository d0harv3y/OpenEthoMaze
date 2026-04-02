"""
Trial data-quality checks for shared offline processing.

These checks stay intentionally narrow: missing files, missing frame counts,
task-specific frame mismatch rules, and missing tracking outputs when a path
was recorded. Behavioral failures do not belong here.
"""

from __future__ import annotations

from typing import Optional

from .io.file_discovery import TrialManifest

# Reason codes stored in DB and reported to user
REASON_MISSING_VIDEO = "missing_video"
REASON_MISSING_FRAME_COUNTS = "missing_frame_counts"
REASON_FRAME_MISMATCH = "frame_mismatch"
REASON_MISSING_SLEAP = "missing_sleap"
REASON_NO_TRACKING = "no_tracking"  # Set from process_trial when SLEAP and realtime xy both unavailable
REASON_PROCESSING_ERROR = "processing_error"  # Set from process_trial when an exception occurs
REASON_NO_EXIT_XY = "no_exit_xy"  # Experimental trial with no exit number/coords in H5; used arena center


def detect_trial_data_quality(
    manifest: TrialManifest,
    *,
    expected_frame_diff: int | None,
) -> Optional[str]:
    """
    Detect whether a trial is missing required offline inputs.

    Args:
        manifest: Trial manifest with paths and frame counts.
        expected_frame_diff: Expected ``video_n_frames - h5_n_frames`` delta for
            the task, or ``None`` when the task does not enforce one.

    Returns:
        A mistrial reason code string, or ``None`` if the trial looks processable.
    """
    if manifest.video_path is None or not manifest.video_path.exists():
        return REASON_MISSING_VIDEO

    if manifest.h5_n_frames is None or manifest.video_n_frames is None:
        return REASON_MISSING_FRAME_COUNTS

    if expected_frame_diff is not None:
        if (manifest.video_n_frames - manifest.h5_n_frames) != expected_frame_diff:
            return REASON_FRAME_MISMATCH

    if manifest.sleap_path is not None and not manifest.sleap_path.exists():
        return REASON_MISSING_SLEAP

    return None
