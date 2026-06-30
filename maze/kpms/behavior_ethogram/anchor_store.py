"""On-disk is_moving anchor artifact (S1 seam parallel to BehaviorLabeling)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import h5py
import numpy as np

from maze.kpms.behavior_ethogram.paths import (
    anchor_frames_h5,
    anchor_provenance_json,
)
from maze.kpms.io import write_json

ANCHOR_SCHEMA_VERSION = "is_moving_anchor_v1"


def missing_is_moving_anchor_files(artifact_dir: Path | str) -> tuple[str, ...]:
    d = Path(artifact_dir)
    missing: list[str] = []
    if not anchor_provenance_json(d).is_file():
        missing.append("provenance.json")
    if not anchor_frames_h5(d).is_file():
        missing.append("anchor_frames.h5")
    return tuple(missing)


@dataclass(frozen=True, eq=False)
class TrialAnchorFrames:
    trial_key: str
    source_frame_index: np.ndarray
    is_moving: np.ndarray

    def __post_init__(self) -> None:
        sfi = np.asarray(self.source_frame_index, dtype=np.int64).ravel()
        im = np.asarray(self.is_moving, dtype=bool).ravel()
        if len(sfi) != len(im):
            raise ValueError("source_frame_index and is_moving must share length")
        if len(sfi) and np.any(np.diff(sfi) <= 0):
            raise ValueError("source_frame_index must be strictly increasing")
        object.__setattr__(self, "source_frame_index", sfi)
        object.__setattr__(self, "is_moving", im)


@dataclass(frozen=True, eq=False)
class IsMovingAnchor:
    calibration_id: str
    fps: float
    trials: tuple[TrialAnchorFrames, ...]
    params: Mapping[str, object] = field(default_factory=dict)
    input_hashes: Mapping[str, str] = field(default_factory=dict)


def _write_frames_h5(path: Path, anchor: IsMovingAnchor) -> None:
    with h5py.File(path, "w") as f:
        f.attrs["schema"] = ANCHOR_SCHEMA_VERSION
        f.attrs["calibration_id"] = anchor.calibration_id
        f.attrs["fps"] = float(anchor.fps)
        trials_grp = f.create_group("trials")
        for i, trial in enumerate(anchor.trials):
            tg = trials_grp.create_group(f"t{i:06d}")
            tg.attrs["trial_key"] = trial.trial_key
            tg.create_dataset(
                "source_frame_index",
                data=trial.source_frame_index.astype(np.int64, copy=False),
                compression="gzip",
            )
            tg.create_dataset(
                "is_moving",
                data=trial.is_moving.astype(np.uint8, copy=False),
                compression="gzip",
            )


def _read_frames_h5(path: Path) -> list[TrialAnchorFrames]:
    trials: list[TrialAnchorFrames] = []
    with h5py.File(path, "r") as f:
        trials_grp = f["trials"]
        for name in sorted(trials_grp.keys()):
            tg = trials_grp[name]
            trials.append(
                TrialAnchorFrames(
                    trial_key=str(tg.attrs["trial_key"]),
                    source_frame_index=tg["source_frame_index"][()],
                    is_moving=np.asarray(tg["is_moving"][()], dtype=bool),
                )
            )
    return trials


def _provenance_payload(anchor: IsMovingAnchor) -> dict:
    n_moving = int(sum(int(np.sum(t.is_moving)) for t in anchor.trials))
    return {
        "schema": ANCHOR_SCHEMA_VERSION,
        "calibration_id": anchor.calibration_id,
        "fps": float(anchor.fps),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_trials": len(anchor.trials),
        "n_moving_frames": n_moving,
        "params": dict(anchor.params),
        "input_hashes": dict(anchor.input_hashes),
    }


def write_is_moving_anchor(artifact_dir: Path | str, anchor: IsMovingAnchor) -> None:
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_frames_h5(anchor_frames_h5(artifact_dir), anchor)
    write_json(anchor_provenance_json(artifact_dir), _provenance_payload(anchor))


def read_is_moving_anchor(artifact_dir: Path | str) -> IsMovingAnchor:
    artifact_dir = Path(artifact_dir)
    missing = missing_is_moving_anchor_files(artifact_dir)
    if missing:
        raise FileNotFoundError(
            f"Not an is_moving anchor artifact dir: {artifact_dir}\n"
            f"Missing: {', '.join(missing)}\n"
            "Expected: anchor_frames.h5 + provenance.json\n"
            "Build with: uv run maze-build-is-moving-anchor --legacy-db ... --manifest-path ..."
        )
    with anchor_provenance_json(artifact_dir).open(encoding="utf-8") as f:
        prov = json.load(f)
    trials = _read_frames_h5(anchor_frames_h5(artifact_dir))
    return IsMovingAnchor(
        calibration_id=str(prov["calibration_id"]),
        fps=float(prov["fps"]),
        trials=tuple(trials),
        params=dict(prov.get("params", {})),
        input_hashes=dict(prov.get("input_hashes", {})),
    )
