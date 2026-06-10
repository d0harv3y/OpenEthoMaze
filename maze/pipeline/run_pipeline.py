"""
Batch orchestration for the maze pipeline.

Coordinates filtering, mistrial handling, and sequential or parallel execution across
the set of trials discovered in the results database.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from tqdm import tqdm

from .paths import MAX_WORKERS, OUTPUT_H5, PARALLEL_ENABLED
from .io.file_discovery import TrialManifest
from .db import (
    TrialKey,
    init_database,
    list_trials,
    open_db,
    read_arena_type,
    write_mistrial_reason,
)
from .trial_filters import (
    GUI_DEFAULT_PREFILTER_MODE,
    PrefilterMode,
    detect_task_mistrial,
    expected_frame_diff,
    trial_matches_frame_policy,
)
from .process_trial import process_trial
from .run_provenance import provenance_run


def _attr_str(attrs, key: str) -> str:
    """Get attribute as string; decode bytes if needed."""
    v = attrs.get(key, "")
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return "" if v is None else str(v)


def _attr_int(attrs, key: str) -> Optional[int]:
    """Get attribute as int; return None if missing or invalid."""
    v = attrs.get(key, None)
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def load_trial_manifests_from_db(db_path: Path) -> list[TrialManifest]:
    """
    Load trial manifests from the output database (no input H5 or file scan).
    Requires init_db to have been run so trial groups and attrs exist.
    Populates h5_n_frames and video_n_frames from trial attrs when present (for frame_diff filtering).
    """
    keys = list_trials(db_path)
    manifests = []
    with open_db(db_path, "r") as h5:
        for key in keys:
            g = h5[key.path()]
            attrs = g.attrs
            video_path_str = _attr_str(attrs, "video_path")
            sleap_path_str = _attr_str(attrs, "sleap_path")
            input_h5_str = _attr_str(attrs, "input_h5_path")
            h5_n_frames = _attr_int(attrs, "h5_n_frames")
            video_n_frames = _attr_int(attrs, "video_n_frames")
            manifests.append(
                TrialManifest(
                    animal_id=key.animal_id,
                    session=key.session,
                    trial=key.trial,
                    input_h5_path=Path(input_h5_str) if input_h5_str else Path(""),
                    video_path=Path(video_path_str) if video_path_str else None,
                    sleap_path=Path(sleap_path_str) if sleap_path_str else None,
                    is_habituation=(key.phase == "habituation"),
                    h5_n_frames=h5_n_frames,
                    video_n_frames=video_n_frames,
                )
            )
    return manifests


def run_pipeline(
    db_path: Optional[Path] = None,
    animal_ids: Optional[list[str]] = None,
    phase: Optional[str] = None,
    sessions: Optional[list[str]] = None,
    trial_names: Optional[list[str]] = None,
    parallel: bool = PARALLEL_ENABLED,
    max_workers: int = MAX_WORKERS,
    generate_qc: bool = True,
    skip_mistrials: bool = True,
    analysis_profile: Optional[tuple[Any, Any]] = None,
    prefilter_mode: PrefilterMode = GUI_DEFAULT_PREFILTER_MODE,
    overwrite_pose: bool = False,
) -> dict[str, int]:
    """
    Run the pipeline on all discovered trials.

    Args:
        db_path: Output database path (uses config default if None)
        animal_ids: Optional list of animal IDs to process (None = all)
        phase: Optional phase filter ("habituation" or "experimental")
        sessions: Optional list of session keys to process (None = all)
        trial_names: Optional list of trial keys to process (None = all)
        parallel: Whether to process in parallel
        max_workers: Maximum parallel workers
        generate_qc: Whether to generate QC visualizations
        skip_mistrials: If True, skip trials with missing data and write mistrial_reason to DB
        analysis_profile: Optional ``(AnalysisTrajectoryConfig, AnalysisTraceQualityConfig)`` tuple
        prefilter_mode: Input-quality prefilter behavior:
            - ``legacy``: enforce frame/file preflight checks
            - ``controller``: bypass preflight blockers (x/y-only analysis allowed)
            - ``auto``: infer from manifest source (default)

    Returns:
        Dictionary with processing statistics
    """
    db_path = db_path or OUTPUT_H5
    db_path = Path(db_path)

    prov_inputs = {
        "db_path": str(db_path),
        "animal_ids": animal_ids,
        "phase": phase,
        "sessions": sessions,
        "trial_names": trial_names,
        "parallel": parallel,
        "max_workers": max_workers,
        "generate_qc": generate_qc,
        "skip_mistrials": skip_mistrials,
        "prefilter_mode": prefilter_mode,
        "has_analysis_profile": analysis_profile is not None,
        "overwrite_pose": overwrite_pose,
    }

    with provenance_run("run_pipeline", db_path, prov_inputs) as prov:
        print("Initializing database...")
        init_database(db_path)
        arena_type = read_arena_type(db_path)

        print("Loading trial list from database...")
        trials = load_trial_manifests_from_db(db_path)
        if not trials:
            print("No trials in database. Run init_db first to populate from input H5 and videos.")
            stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
            prov["outputs"] = stats
            return stats

        if animal_ids is not None:
            trials = [t for t in trials if t.animal_id in animal_ids]

        if phase is not None:
            trials = [t for t in trials if t.phase == phase]

        if sessions is not None and len(sessions) > 0:
            trials = [t for t in trials if t.session in sessions]

        if trial_names is not None and len(trial_names) > 0:
            trials = [t for t in trials if t.trial in trial_names]

        n_before_frame_filter = len(trials)
        trials = [
            t
            for t in trials
            if trial_matches_frame_policy(
                t,
                arena_type,
                mode=prefilter_mode,
            )
        ]
        n_excluded_frame_diff = n_before_frame_filter - len(trials)
        if n_excluded_frame_diff > 0:
            expected_diff = expected_frame_diff(arena_type)
            if expected_diff is None:
                print(f"Excluded {n_excluded_frame_diff} trial(s) by task-specific frame policy.")
            else:
                print(
                    f"Excluded {n_excluded_frame_diff} trial(s) where frame_diff "
                    f"(video - h5) != {expected_diff}."
                )

        if not trials:
            print("No trials match the given filters after task-specific frame filtering.")
            stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
            prov["outputs"] = {**stats, "n_excluded_frame_diff": n_excluded_frame_diff}
            return stats

        mistrial_trials: list[tuple[TrialManifest, str]] = []
        processable: list[TrialManifest] = []
        for trial in trials:
            reason = detect_task_mistrial(
                trial,
                arena_type,
                mode=prefilter_mode,
            )
            if reason is not None:
                mistrial_trials.append((trial, reason))
            else:
                processable.append(trial)

        if skip_mistrials and mistrial_trials:
            for trial, reason in mistrial_trials:
                key = TrialKey.from_manifest(trial)
                write_mistrial_reason(db_path, key, reason)
            reason_counts: dict[str, int] = {}
            for _, reason in mistrial_trials:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            print(
                f"Skipping {len(mistrial_trials)} trial(s) with missing data (mistrial): "
                + ", ".join(
                    f"{reason}: {count}" for reason, count in sorted(reason_counts.items())
                )
            )
            trials = processable

        n_skipped_mistrial = len(mistrial_trials) if skip_mistrials else 0

        if not trials:
            print("No trials left after mistrial filter.")
            stats = {"total": 0, "success": 0, "failed": 0, "skipped": n_skipped_mistrial}
            prov["outputs"] = stats
            return stats

        print(f"Processing {len(trials)} trials...")

        stats = {
            "total": len(trials),
            "success": 0,
            "failed": 0,
            "skipped": n_skipped_mistrial,
        }

        if parallel and max_workers > 1:
            stats = _run_parallel(
                trials,
                db_path,
                max_workers,
                generate_qc,
                stats,
                analysis_profile,
                overwrite_pose,
            )
        else:
            stats = _run_sequential(
                trials, db_path, generate_qc, stats, analysis_profile, overwrite_pose
            )

        print("\nPipeline complete:")
        print(f"  Total: {stats['total']}")
        print(f"  Success: {stats['success']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Skipped: {stats['skipped']}")

        prov["outputs"] = {
            **stats,
            "n_excluded_frame_diff": n_excluded_frame_diff,
            "arena_type": arena_type,
        }
        return stats


class _TqdmHandler(logging.Handler):
    """Send log records to tqdm.write so the progress bar is not overwritten."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            tqdm.write(msg)
        except Exception:
            self.handleError(record)


def _run_sequential(
    trials: list[TrialManifest],
    db_path: Path,
    generate_qc: bool,
    stats: dict[str, int],
    analysis_profile: Optional[tuple[Any, Any]] = None,
    overwrite_pose: bool = False,
) -> dict[str, int]:
    """Run trials sequentially with clean progress display."""
    pipeline_logger = logging.getLogger("maze_pipeline")
    tqdm_handler = _TqdmHandler()
    tqdm_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    pipeline_logger.addHandler(tqdm_handler)
    try:
        return _run_sequential_impl(
            trials, db_path, generate_qc, stats, analysis_profile, overwrite_pose
        )
    finally:
        pipeline_logger.removeHandler(tqdm_handler)


def _run_sequential_impl(
    trials: list[TrialManifest],
    db_path: Path,
    generate_qc: bool,
    stats: dict[str, int],
    analysis_profile: Optional[tuple[Any, Any]] = None,
    overwrite_pose: bool = False,
) -> dict[str, int]:
    """Inner loop for sequential processing."""
    pbar = tqdm(trials, desc="Processing", unit="trial")

    for trial in pbar:
        trial_key = f"{trial.animal_id}/{trial.phase[:3]}/{trial.session}/{trial.trial}"
        pbar.set_postfix_str(trial_key, refresh=True)

        try:
            success = process_trial(
                trial,
                db_path=db_path,
                generate_qc=generate_qc,
                quiet=True,
                analysis_profile=analysis_profile,
                overwrite_pose=overwrite_pose,
            )
            if success:
                stats["success"] += 1
            else:
                stats["failed"] += 1
        except Exception as exc:
            tqdm.write(f"Error processing {trial.trial_key}: {exc}")
            stats["failed"] += 1

    return stats


def _run_parallel(
    trials: list[TrialManifest],
    db_path: Path,
    max_workers: int,
    generate_qc: bool,
    stats: dict[str, int],
    analysis_profile: Optional[tuple[Any, Any]] = None,
    overwrite_pose: bool = False,
) -> dict[str, int]:
    """Run trials in parallel."""
    del max_workers
    print("Warning: Parallel mode uses sequential HDF5 writes")
    return _run_sequential(trials, db_path, generate_qc, stats, analysis_profile, overwrite_pose)


def run_single_trial(
    animal_id: str,
    session: str,
    trial: str,
    db_path: Optional[Path] = None,
    generate_qc: bool = True,
    phase: Optional[str] = None,
    analysis_profile: Optional[tuple[Any, Any]] = None,
) -> bool:
    """
    Run pipeline on a single trial.

    Args:
        animal_id: Animal ID
        session: Session key (e.g., "S01")
        trial: Trial key (e.g., "T01")
        db_path: Output database path
        generate_qc: Whether to generate QC visualizations
        phase: If set ("habituation" or "experimental"), only consider that phase
        analysis_profile: Optional ``(AnalysisTrajectoryConfig, AnalysisTraceQualityConfig)`` tuple

    Returns:
        True if processing succeeded
    """
    db_path = db_path or OUTPUT_H5

    init_database(db_path)
    trials = load_trial_manifests_from_db(db_path)
    if not trials:
        print("No trials in database. Run init_db first.")
        return False

    matching = [
        trial_manifest
        for trial_manifest in trials
        if trial_manifest.animal_id == animal_id
        and trial_manifest.session == session
        and trial_manifest.trial == trial
    ]
    if phase is not None:
        matching = [trial_manifest for trial_manifest in matching if trial_manifest.phase == phase]

    if not matching:
        message = f"Trial not found: {animal_id}/{session}/{trial}"
        if phase is not None:
            message += f" (phase={phase})"
        print(message)
        return False

    manifest = matching[0]
    return process_trial(
        manifest,
        db_path=db_path,
        generate_qc=generate_qc,
        analysis_profile=analysis_profile,
    )


load_manifests_from_db = load_trial_manifests_from_db
