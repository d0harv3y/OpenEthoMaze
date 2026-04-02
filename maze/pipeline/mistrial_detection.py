"""
Mistrial detection for trials with missing or invalid data.

Uses conservative, objective criteria only (missing files, missing frame counts,
frame mismatch). Does not infer behavioral mistrials.
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


def detect_mistrial(manifest: TrialManifest) -> Optional[str]:
    """
    Detect if a trial has missing data that makes it unsuitable for processing.

    Criteria are conservative: only obvious missing data (no video, no frame
    counts, frame count mismatch, or SLEAP file missing when path is set).
    Returns the first reason found, or None if the trial looks processable.

    Args:
        manifest: Trial manifest with paths and frame counts.

    Returns:
        Reason code string (e.g. "missing_video"), or None if no mistrial detected.
    """
    # Missing or non-existent video
    if manifest.video_path is None:
        return REASON_MISSING_VIDEO
    if not manifest.video_path.exists():
        return REASON_MISSING_VIDEO

    # Missing frame counts (needed for alignment and frame_diff check)
    if manifest.h5_n_frames is None or manifest.video_n_frames is None:
        return REASON_MISSING_FRAME_COUNTS

    # Expected off-by-one: video has one fewer frame than H5
    if (manifest.video_n_frames - manifest.h5_n_frames) != -1:
        return REASON_FRAME_MISMATCH

    # SLEAP path set but file missing (tracking data expected but not present)
    if manifest.sleap_path is not None and not manifest.sleap_path.exists():
        return REASON_MISSING_SLEAP

    return None
