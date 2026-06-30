"""Build is_moving anchor artifacts from legacy VAST speed."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import h5py
import numpy as np

from maze.kpms.behavior_ethogram.anchor import calibrate_is_moving_params, is_moving
from maze.kpms.behavior_ethogram.anchor_legacy import load_legacy_vast_speed, run_phase_mask
from maze.kpms.behavior_ethogram.anchor_store import IsMovingAnchor, TrialAnchorFrames, write_is_moving_anchor
from maze.kpms.behavior_ethogram.labeling import hash_file
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest


def _trial_fps(legacy_db: Path, manifest: TrialManifest) -> float:
    key = TrialKey.from_manifest(manifest)
    with h5py.File(legacy_db, "r") as h5:
        g = h5[key.path().lstrip("/")]
        return float(g.attrs.get("fps") or g.attrs.get("h5_fps") or 30.0)


def build_is_moving_anchor(
    legacy_db: Path | str,
    manifests: Sequence[TrialManifest],
    artifact_dir: Path | str,
    *,
    calibration_id: str = "default",
    dwell_candidates_ms: tuple[float, ...] = (50.0, 100.0, 150.0, 200.0, 300.0),
) -> IsMovingAnchor:
    """Calibrate on pooled RUN-phase legacy speed, then label each trial."""
    legacy_db = Path(legacy_db)
    loaded_trials = []
    pooled_speeds: list[np.ndarray] = []

    for manifest in manifests:
        loaded = load_legacy_vast_speed(legacy_db, manifest)
        if loaded is None:
            continue
        run_mask = run_phase_mask(loaded.trial_state)
        cal_mask = loaded.valid & run_mask
        pooled_speeds.append(loaded.speed_mps[cal_mask])
        loaded_trials.append(loaded)

    if not loaded_trials:
        raise ValueError("no legacy speed rows loaded from manifests")

    fps = _trial_fps(legacy_db, manifests[0])
    params = calibrate_is_moving_params(
        np.concatenate(pooled_speeds),
        fps=fps,
        dwell_candidates_ms=dwell_candidates_ms,
    )

    trials_out: list[TrialAnchorFrames] = []
    for loaded in loaded_trials:
        run_mask = run_phase_mask(loaded.trial_state)
        mask = is_moving(
            loaded.speed_mps,
            fps=fps,
            enter_mps=params.enter_mps,
            exit_mps=params.exit_mps,
            min_dwell_ms=params.min_dwell_ms,
            valid=loaded.valid,
        )
        mask = mask & run_mask
        trials_out.append(
            TrialAnchorFrames(
                trial_key=loaded.trial_key,
                source_frame_index=loaded.source_frame_index,
                is_moving=mask,
            )
        )

    anchor = IsMovingAnchor(
        calibration_id=calibration_id,
        fps=fps,
        trials=tuple(trials_out),
        params={
            "enter_mps": params.enter_mps,
            "exit_mps": params.exit_mps,
            "min_dwell_ms": params.min_dwell_ms,
        },
        input_hashes={"legacy_db": hash_file(legacy_db)},
    )
    write_is_moving_anchor(artifact_dir, anchor)
    return anchor
