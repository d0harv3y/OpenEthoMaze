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
from typing import TYPE_CHECKING, Any, Optional, Tuple

if TYPE_CHECKING:
    from maze.pipeline.db import TrialKey
    from maze.pipeline.io.file_discovery import TrialManifest

# Phases that mark habituation-style trials for manifest / pipeline labeling.
HABITUATION_RUN_PHASES: frozenset[str] = frozenset({"habituation", "habituation_training"})


def is_habituation_run_phase(run_phase: str) -> bool:
    """True when ``run_phase`` should set ``TrialManifest.is_habituation``."""
    return run_phase in HABITUATION_RUN_PHASES


def run_analysis_for_trial(
    db_path: Path,
    animal_id: str,
    session_id: str,
    trial: str,
    video_path: Path | None,
    run_phase: str,
    analysis_profile: Optional[tuple[Any, Any]] = None,
    overwrite_pose: bool = False,
) -> Tuple[bool, str]:
    """
    Run pipeline process_trial for the given controller-recorded trial.

    Args:
        db_path: Path to the controller H5 (same file the trial was written to).
        animal_id: Animal ID.
        session_id: Session key (e.g. S01).
        trial: Trial key (e.g. T01).
        video_path: Final video path for the trial (may be None if recording was discarded).
        run_phase: Controller ``Settings.run_phase`` at trial stop (task-agnostic string).
            VAST examples: ``habituation``, ``habituation_training``, experimental phases.
            RAM examples: ``radial_arm`` for the maze task, or habituation strings when used.
            Only ``habituation`` and ``habituation_training`` set ``is_habituation`` on the
            manifest; all other values are treated as non-habituation.

    Returns:
        (success, message) for status bar or logging.
    """
    try:
        from maze.pipeline.db.trial_key import TrialKey
        from maze.pipeline.process_trial import process_trial
    except ImportError:
        return (False, "maze.pipeline not available")

    key = TrialKey(animal_id=animal_id, session=session_id, trial=trial)
    manifest = manifest_from_controller_h5(db_path, key)
    if video_path is not None:
        manifest.video_path = video_path
    manifest.is_habituation = is_habituation_run_phase(run_phase)
    ok = process_trial(
        manifest,
        db_path=db_path,
        generate_qc=True,
        quiet=True,
        analysis_profile=analysis_profile,
        overwrite_pose=overwrite_pose,
    )
    if ok:
        return (True, "Analysis done")
    return (False, "Analysis failed (see mistrial_reason in H5)")


def _decode_h5_attr(val: object) -> str:
    if val is None:
        return ""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace").strip()
    return str(val).strip()


def manifest_from_controller_h5(db_path: Path, key: TrialKey) -> TrialManifest:
    """
    Build a :class:`~maze.pipeline.io.file_discovery.TrialManifest` from trial attrs
    in a controller database (``video_path``, ``phase`` / ``stage``).

    ``is_habituation`` follows the same rule as :func:`run_analysis_for_trial`, using
    recorded ``phase`` (else ``stage``) when present; otherwise it defaults to False.
    """
    import h5py

    from maze.pipeline.io.file_discovery import TrialManifest
    from maze.pipeline.video_paths import resolve_video_path

    with h5py.File(db_path, "r") as h5:
        g_trial = h5[key.path()]
        attrs = g_trial.attrs
        vp = _decode_h5_attr(attrs.get("video_path", ""))
        video_path = resolve_video_path(vp) if vp else None
        sp = _decode_h5_attr(attrs.get("sleap_path", ""))
        sleap_path = Path(sp) if sp else None
        phase = _decode_h5_attr(attrs.get("phase", "")) or _decode_h5_attr(attrs.get("stage", ""))
        is_habituation = is_habituation_run_phase(phase)

    return TrialManifest(
        animal_id=key.animal_id,
        session=key.session,
        trial=key.trial,
        input_h5_path=db_path,
        video_path=video_path,
        sleap_path=sleap_path,
        is_habituation=is_habituation,
    )


def reprocess_controller_h5(
    db_path: Path,
    *,
    animal_id: str | None = None,
    session: str | None = None,
    trial: str | None = None,
    generate_qc: bool = True,
    quiet: bool = False,
) -> dict[str, int]:
    """
    Run ``process_trial`` for trials already present in a controller H5 (backfill).

    Filters are optional; omit all to process every trial in the file.

    Returns:
        Counts ``ok``, ``fail`` (pipeline returned False), and ``skipped`` (currently 0;
        reserved for future filters).
    """
    from maze.pipeline.db import list_trials
    from maze.pipeline.process_trial import process_trial

    keys = list_trials(db_path)
    if animal_id is not None:
        keys = [k for k in keys if k.animal_id == animal_id]
    if session is not None:
        keys = [k for k in keys if k.session == session]
    if trial is not None:
        keys = [k for k in keys if k.trial == trial]

    stats = {"ok": 0, "fail": 0, "skipped": 0}
    for key in keys:
        manifest = manifest_from_controller_h5(db_path, key)
        ok = process_trial(
            manifest,
            db_path=db_path,
            generate_qc=generate_qc,
            quiet=quiet,
        )
        if ok:
            stats["ok"] += 1
        else:
            stats["fail"] += 1
    return stats
