"""
Canonical trial HDF5 resolution and anatomical pose load for kpMS (tracking v2).

Read priority per ``docs/h5_tracking_contract.md``:

1. ``manifest.input_h5_path`` when the file exists and holds ``tracking/anatomical``
2. Else ``db_path`` when it holds ``tracking/anatomical`` for the trial
3. Else no canonical H5 pose (caller falls back to ``sleap_path`` in T2b)

No OpenCV dependency — safe to import from kpMS preprocess paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np

from maze.pipeline.db.trial_key import TrialKey, resolve_trial_key_for_hdf5
from maze.pipeline.io.file_discovery import TrialManifest
from maze.pipeline.tracking_io import AnatomicalTrackingData, has_anatomical_tracking, read_anatomical_tracking


@dataclass(frozen=True)
class AnatomicalPoseLoad:
    """Anatomical pose tensors and attrs ready for kpMS preprocess (stream A)."""

    frame_index: np.ndarray
    coordinates: np.ndarray
    confidences: np.ndarray
    node_names: tuple[str, ...]
    pose_source: str
    fps: float
    pose_model_path: str = ""
    valid: np.ndarray | None = None


def _trial_key_from_manifest(manifest: TrialManifest) -> TrialKey:
    return TrialKey(
        animal_id=str(manifest.animal_id),
        session=str(manifest.h5_session),
        trial=str(manifest.trial),
    )


def _manifest_lookup_keys(manifest: TrialManifest) -> tuple[TrialKey, ...]:
    """Candidate HDF5 group keys (session alias tolerance)."""
    primary = _trial_key_from_manifest(manifest)
    alt = TrialKey.from_manifest(manifest)
    if alt == primary:
        return (primary,)
    return (primary, alt)


def _normalized_input_h5_path(manifest: TrialManifest) -> Path | None:
    raw = str(getattr(manifest, "input_h5_path", "") or "").strip()
    if not raw:
        return None
    return Path(raw)


def h5_has_anatomical_tracking(h5_path: Path | str, trial_key: TrialKey) -> bool:
    """Return True when ``h5_path`` contains ``tracking/anatomical`` for ``trial_key``."""
    path = Path(h5_path)
    if not path.is_file():
        return False
    try:
        with h5py.File(path, "r") as h5:
            resolved = resolve_trial_key_for_hdf5(h5, trial_key)
            group_path = resolved.path().lstrip("/")
            if group_path not in h5:
                return False
            return has_anatomical_tracking(h5[group_path])
    except OSError:
        return False


def resolve_canonical_trial_h5(
    manifest: TrialManifest,
    db_path: Path | str,
) -> Path | None:
    """
    Resolve the HDF5 file that holds ``tracking/anatomical`` for a manifest row.

    Returns ``None`` when neither ``input_h5_path`` nor ``db_path`` contains pose.
    """
    keys = _manifest_lookup_keys(manifest)
    candidates: list[Path] = []
    input_h5 = _normalized_input_h5_path(manifest)
    if input_h5 is not None:
        candidates.append(input_h5)
    db = Path(db_path)
    if db not in candidates:
        candidates.append(db)

    for candidate in candidates:
        for key in keys:
            if h5_has_anatomical_tracking(candidate, key):
                return candidate.resolve()
    return None


def _parse_trial_key(trial_key: TrialKey | str) -> TrialKey:
    if isinstance(trial_key, TrialKey):
        return trial_key
    parts = str(trial_key).strip("/").split("/")
    if len(parts) != 3:
        raise ValueError(f"trial_key must be animal/session/trial, got {trial_key!r}")
    return TrialKey(animal_id=parts[0], session=parts[1], trial=parts[2])


def _anatomical_to_pose_load(data: AnatomicalTrackingData) -> AnatomicalPoseLoad:
    t = int(data.frame_index.shape[0])
    k = len(data.node_names)
    coordinates = np.stack([data.x, data.y], axis=-1).astype(np.float32, copy=False)
    if coordinates.shape != (t, k, 2):
        coordinates = np.full((t, k, 2), np.nan, dtype=np.float32)
        coordinates[:, :, 0] = data.x
        coordinates[:, :, 1] = data.y
    confidences = np.asarray(data.score, dtype=np.float32)
    valid = None if data.valid is None else np.asarray(data.valid, dtype=np.uint8)
    return AnatomicalPoseLoad(
        frame_index=np.asarray(data.frame_index, dtype=np.uint32),
        coordinates=coordinates,
        confidences=confidences,
        node_names=data.node_names,
        pose_source=data.pose_source,
        fps=float(data.fps),
        pose_model_path=data.pose_model_path,
        valid=valid,
    )


def load_anatomical_from_h5(
    path: Path | str,
    trial_key: TrialKey | str,
) -> AnatomicalPoseLoad | None:
    """
    Load ``tracking/anatomical`` from ``path`` for ``trial_key``.

    Returns ``None`` when the trial group or anatomical datasets are absent (v1 files).
    """
    h5_path = Path(path)
    if not h5_path.is_file():
        return None

    key = _parse_trial_key(trial_key)
    try:
        with h5py.File(h5_path, "r") as h5:
            resolved = resolve_trial_key_for_hdf5(h5, key)
            group_path = resolved.path().lstrip("/")
            if group_path not in h5:
                return None
            data = read_anatomical_tracking(h5[group_path])
            if data is None:
                return None
            return _anatomical_to_pose_load(data)
    except OSError:
        return None
