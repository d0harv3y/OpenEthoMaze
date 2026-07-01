"""Compile bout scalar table from anatomical kpMS apply + trial H5.

Output columns: ``docs/bout_feature_contract.md`` (schema ``bout_feature_v2``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import h5py
import numpy as np

from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.kpms.frame_alignment import (
    KpmsAlignmentCache,
    kpms_aligned_coordinates_and_indices,
    kpms_recording_key,
)
from maze.kpms.heading_idxs import anterior_posterior_idxs
from maze.kpms.h5_pose import load_blob_from_h5, resolve_canonical_trial_h5
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest

from .bout_kinematics import (
    abs_dheading_per_frame,
    blob_area_px2_for_rows,
    centroid_from_coordinates,
    heading_from_anterior_posterior,
    speed_mps_from_centroid,
    trial_state_for_rows,
)
from .bout_scalars import BoutScalarFeatures, compile_trial_bout_features
from .bout_table_io import bout_row_to_dict


@dataclass(frozen=True)
class CompileBoutFeaturesConfig:
    stream: str = "anatomical"
    include_heading_direction: bool = False
    fps: float = 30.0
    px_per_cm: float = 2.42


def _load_syllables_from_h5(results_h5: h5py.File, recording_key: str) -> np.ndarray | None:
    if recording_key not in results_h5:
        return None
    rec = results_h5[recording_key]
    if "syllable" not in rec:
        return None
    return np.asarray(rec["syllable"], dtype=np.int64)


def _load_syllables(results_h5: Path, recording_key: str) -> np.ndarray | None:
    with h5py.File(results_h5, "r") as h5:
        return _load_syllables_from_h5(h5, recording_key)


def _load_trial_states_legacy_h5(
    legacy_h5: h5py.File | None,
    manifest: TrialManifest,
) -> np.ndarray | None:
    if legacy_h5 is None:
        return None
    key = TrialKey.from_manifest(manifest)
    group_path = key.path().lstrip("/")
    if group_path not in legacy_h5:
        return None
    g = legacy_h5[group_path]
    for point in ("spot_hybrid", "center"):
        xy_path = f"ambulation_metrics/{point}/xy"
        if xy_path not in g:
            continue
        rec = g[xy_path]
        if "trial_state" in rec.dtype.names:
            return np.asarray(rec["trial_state"])
    return None


def _load_trial_states_legacy(legacy_db: Path, manifest: TrialManifest) -> np.ndarray | None:
    with h5py.File(legacy_db, "r") as h5:
        return _load_trial_states_legacy_h5(h5, manifest)


def compile_trial_bouts(
    manifest: TrialManifest,
    *,
    results_h5: h5py.File,
    seed: str,
    cfg: CompileBoutFeaturesConfig,
    pre_cfg: KpmsPreprocessConfig,
    legacy_h5: h5py.File | None = None,
    alignment_cache: KpmsAlignmentCache | None = None,
) -> list[dict]:
    recording_key = kpms_recording_key(manifest)
    z = _load_syllables_from_h5(results_h5, recording_key)
    if z is None or len(z) == 0:
        return []

    if alignment_cache is not None:
        aligned = alignment_cache.aligned_trial(manifest, pre_cfg)
        if aligned is None:
            return []
        coordinates = aligned.coordinates
        frame_idx = aligned.source_frame_indices
    else:
        aligned_out = kpms_aligned_coordinates_and_indices(manifest, pre_cfg)
        if aligned_out is None:
            return []
        _rk, coordinates, frame_idx = aligned_out
    if len(coordinates) != len(z):
        return []

    anterior, posterior = anterior_posterior_idxs(STANDARD_NODE_NAMES, pose_stream="anatomical")
    centroid = centroid_from_coordinates(coordinates)
    speed = speed_mps_from_centroid(
        centroid, fps=cfg.fps, px_per_cm=pre_cfg.px_per_cm or cfg.px_per_cm
    )
    heading = heading_from_anterior_posterior(
        coordinates,
        anterior_idx=int(anterior[0]),
        posterior_idx=int(posterior[0]),
    )
    abs_dheading = abs_dheading_per_frame(heading)

    blob_area = np.full(len(z), np.nan, dtype=np.float64)
    db_path = pre_cfg.db_path if pre_cfg.db_path is not None else Path()
    h5_path = resolve_canonical_trial_h5(manifest, db_path)
    if h5_path is not None:
        trial_key = TrialKey.from_manifest(manifest)
        blob = load_blob_from_h5(h5_path, trial_key)
        if blob is not None:
            blob_area = blob_area_px2_for_rows(blob.coordinates, blob.valid, frame_idx)

    trial_states: list[str] | None = None
    raw_states = _load_trial_states_legacy_h5(legacy_h5, manifest)
    if raw_states is not None:
        trial_states = trial_state_for_rows(raw_states, frame_idx)

    feats: list[BoutScalarFeatures] = compile_trial_bout_features(
        z,
        speed_mps=speed,
        abs_dheading=abs_dheading,
        blob_area_px2=blob_area,
        heading_rad=heading,
        centroid_xy_px=centroid,
        fps=cfg.fps,
        trial_states=trial_states,
        include_heading_direction=cfg.include_heading_direction,
    )
    return [
        bout_row_to_dict(
            f,
            stream=cfg.stream,
            seed=seed,
            trial_key=recording_key,
        )
        for f in feats
    ]


def filter_manifests_with_results_h5(
    manifests: Sequence[TrialManifest],
    results_h5: Path,
) -> list[TrialManifest]:
    """Keep manifest rows whose kpMS recording key exists in ``results_apply.h5``."""
    with h5py.File(results_h5, "r") as h5:
        keys = set(h5.keys())
    return [m for m in manifests if kpms_recording_key(m) in keys]


def compile_cohort_bout_features(
    manifests: Sequence[TrialManifest],
    *,
    kpms_root: Path,
    seed: str,
    cfg: CompileBoutFeaturesConfig | None = None,
    pre_cfg: KpmsPreprocessConfig | None = None,
    legacy_db: Path | None = None,
    alignment_cache: KpmsAlignmentCache | None = None,
) -> list[dict]:
    cfg = cfg or CompileBoutFeaturesConfig()
    pre_cfg = pre_cfg or KpmsPreprocessConfig()
    results_h5 = Path(kpms_root) / "anatomical" / f"seed_{seed}" / "results_apply.h5"
    if not results_h5.is_file():
        raise FileNotFoundError(f"missing results_apply.h5 for seed {seed}: {results_h5}")

    cohort_manifests = filter_manifests_with_results_h5(list(manifests), results_h5)
    rows: list[dict] = []
    legacy_h5: h5py.File | None = None
    if legacy_db is not None and legacy_db.is_file():
        legacy_h5 = h5py.File(legacy_db, "r")
    try:
        with h5py.File(results_h5, "r") as results_h5_file:
            for manifest in cohort_manifests:
                rows.extend(
                    compile_trial_bouts(
                        manifest,
                        results_h5=results_h5_file,
                        seed=seed,
                        cfg=cfg,
                        pre_cfg=pre_cfg,
                        legacy_h5=legacy_h5,
                        alignment_cache=alignment_cache,
                    )
                )
    finally:
        if legacy_h5 is not None:
            legacy_h5.close()
    return rows
