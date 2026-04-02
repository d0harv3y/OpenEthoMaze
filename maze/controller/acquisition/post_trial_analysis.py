"""
Run maze pipeline analysis (metrics, heatmap, movement bouts) for a single trial.

Used when run_analysis_after_trial is enabled: after the controller finishes
writing a trial to H5, we run the pipeline's process_trial in a background
thread so results are ready without a separate batch step.

Requires maze.pipeline to be importable. If the import fails, run_analysis_for_trial returns
(False, "maze.pipeline not available").

The pipeline uses the same H5 layout as the controller: /animal_id/session/trial,
so no path translation or copy is needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple


def run_analysis_for_trial(
    db_path: Path,
    animal_id: str,
    session_id: str,
    trial: str,
    video_path: Path | None,
    run_phase: str,
) -> Tuple[bool, str]:
    """
    Run pipeline process_trial for the given controller-recorded trial.

    Args:
        db_path: Path to the controller H5 (same file the trial was written to).
        animal_id: Animal ID.
        session_id: Session key (e.g. S01).
        trial: Trial key (e.g. T01).
        video_path: Final video path for the trial (may be None if recording was discarded).
        run_phase: Controller run_phase (habituation | habituation_training | VAST).

    Returns:
        (success, message) for status bar or logging.
    """
    try:
        from maze.pipeline.io.file_discovery import TrialManifest
        from maze.pipeline.process_trial import process_trial
    except ImportError:
        return (False, "maze.pipeline not available")

    is_habituation = run_phase in ("habituation", "habituation_training")
    manifest = TrialManifest(
        animal_id=animal_id,
        session=session_id,
        trial=trial,
        input_h5_path=db_path,
        video_path=video_path,
        sleap_path=None,
        is_habituation=is_habituation,
    )
    ok = process_trial(
        manifest,
        db_path=db_path,
        generate_qc=True,
        quiet=True,
    )
    if ok:
        return (True, "Analysis done")
    return (False, "Analysis failed (see mistrial_reason in H5)")
