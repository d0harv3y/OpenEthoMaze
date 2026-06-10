"""
Build a controller-parity results H5 with ``tracking/anatomical`` and ``tracking/blob``.

Minimal trial attrs (paths + labels only) — no legacy exit/center ambulation pipeline.
Intended for kpMS fit streams A/B/C on cohorts discovered from video + SLEAP sidecars.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from maze.pipeline.db import (
    TrialKey,
    ensure_trial_group,
    init_database,
    write_animal_label,
    write_trial_frame_counts,
    write_trial_manifest_rows,
)
from maze.pipeline.io.file_discovery import (
    DiscoveryResult,
    TrialManifest,
    enrich_manifests_has_tracking_pose,
    save_manifest_csv,
)
from maze.pipeline.offline_tracking import OfflineBlobParams, materialize_blob_buffer_from_video
from maze.pipeline.persist_pose import persist_pose_from_sidecar
from maze.pipeline.tracking_io import has_anatomical_tracking, has_blob_tracking, read_anatomical_tracking


@dataclass
class BuildTrackingH5Stats:
    """Per-trial materialization counts."""

    trials_total: int = 0
    anatomical_written: int = 0
    anatomical_skipped: int = 0
    anatomical_failed: int = 0
    blob_written: int = 0
    blob_skipped: int = 0
    blob_failed: int = 0
    errors: list[str] = field(default_factory=list)


def manifest_path_for_db(db_path: Path) -> Path:
    return db_path.parent / f"trial_manifest_{db_path.stem}.csv"


def _prepare_manifests_for_db(
    trials: list[TrialManifest],
    db_path: Path,
) -> list[TrialManifest]:
    """Point manifest rows at the output H5 (controller-first canonical path)."""
    resolved = db_path.resolve()
    out: list[TrialManifest] = []
    for trial in trials:
        trial.input_h5_path = resolved
        out.append(trial)
    return out


def build_tracking_h5(
    db_path: Path,
    trials: Sequence[TrialManifest],
    *,
    skip_anatomical: bool = False,
    skip_blob: bool = False,
    overwrite_pose: bool = False,
    overwrite_blob: bool = False,
    blob_params: OfflineBlobParams | None = None,
    log: Callable[[str], None] | None = None,
) -> BuildTrackingH5Stats:
    """
    Create or update ``db_path`` with kpMS-ready ``tracking/`` groups.

    Anatomical: ``persist_pose_from_sidecar`` when ``trial.sleap_path`` exists.
    Blob: offline re-track from ``trial.video_path`` when OpenCV is available.

    Also writes animal labels from discovery metadata and ``metadata/trial_manifest``.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists() or db_path.stat().st_size == 0:
        init_database(db_path)

    manifests = _prepare_manifests_for_db(list(trials), db_path)
    stats = BuildTrackingH5Stats(trials_total=len(manifests))

    unique_animals: set[str] = set()
    for trial in manifests:
        animal_id = trial.effective_animal_id
        if animal_id not in unique_animals:
            unique_animals.add(animal_id)
            write_animal_label(
                db_path,
                animal_id,
                strain=trial.strain,
                experiment=trial.experiment,
                sex=trial.sex,
                tx=trial.tx,
                researcher=trial.researcher,
                drug=trial.drug,
            )

    import h5py

    for trial in manifests:
        key = TrialKey.from_manifest(trial)
        ensure_trial_group(
            db_path,
            key,
            video_path=str(trial.video_path) if trial.video_path else None,
            sleap_path=str(trial.sleap_path) if trial.sleap_path else None,
            input_h5_path=str(db_path.resolve()),
        )

        if trial.h5_n_frames is not None and trial.video_n_frames is not None:
            try:
                write_trial_frame_counts(db_path, key, trial.h5_n_frames, trial.video_n_frames)
            except Exception:
                pass

        if not skip_anatomical and trial.sleap_path is not None and trial.sleap_path.is_file():
            result = persist_pose_from_sidecar(
                db_path,
                key,
                trial.sleap_path,
                overwrite_pose=overwrite_pose,
            )
            if result.action == "written":
                stats.anatomical_written += 1
            elif result.action in ("kept_live", "unchanged"):
                stats.anatomical_skipped += 1
            else:
                stats.anatomical_failed += 1
                msg = f"{key.path()}: anatomical {result.action}"
                stats.errors.append(msg)
                if log:
                    log(msg)
        elif not skip_anatomical:
            stats.anatomical_skipped += 1

        if skip_blob:
            continue
        if trial.video_path is None or not trial.video_path.is_file():
            stats.blob_skipped += 1
            continue

        with h5py.File(db_path, "a") as h5:
            g_trial = h5[key.path()]
            if has_blob_tracking(g_trial) and not overwrite_blob:
                stats.blob_skipped += 1
                continue

        anatomical = None
        if not skip_anatomical:
            with h5py.File(db_path, "r") as h5:
                g_trial = h5[key.path()]
                if has_anatomical_tracking(g_trial):
                    anatomical = read_anatomical_tracking(g_trial)

        try:
            buffer, _fps = materialize_blob_buffer_from_video(
                trial.video_path,
                anatomical=anatomical,
                params=blob_params,
            )
            with h5py.File(db_path, "a") as h5:
                g_trial = h5[key.path()]
                flushed = buffer.flush(g_trial, h5=h5)
            if flushed is not None:
                stats.blob_written += 1
            else:
                stats.blob_skipped += 1
        except Exception as exc:
            stats.blob_failed += 1
            msg = f"{key.path()}: blob {type(exc).__name__}: {exc}"
            stats.errors.append(msg)
            if log:
                log(msg)

    enrich_manifests_has_tracking_pose(manifests, db_path=db_path)
    write_trial_manifest_rows(db_path, manifests)
    save_manifest_csv(DiscoveryResult(trials=manifests), manifest_path_for_db(db_path))

    return stats


def default_kpms_tracking_db(repo_root: Path) -> Path:
    """Default output H5 for ``maze-legacy-db build-kpms-h5``."""
    return repo_root / "outputs" / "legacy" / "kpms_tracking.h5"
