"""Producer-agnostic Behavior labeling artifact (S0 contract).

Every Behavior **producer** (Option A syllable-sequence grammar, Option B
B-SOiD/MotionMapper frame states, Option D enriched bout AR-HMM) emits this
same artifact so a single evaluation harness can score them on equal footing:

  - ``behavior_frames.h5`` — per-frame Behavior labels on the SOURCE video frame
    timeline (one group per trial: ``source_frame_index`` + ``behavior_id``).
  - ``behavior_bouts.csv`` — derived bout-level table (run-length encoding of the
    per-frame stream). Matches the existing "per-frame in store, bout in CSV"
    grain from ``docs/ethogram_scope.md``.
  - ``provenance.json`` — producer, params, fit/seed ids, input hashes, fps.

This module is foundational. It must not import producer-specific code
(``bout_scalars``, ``arhmm``, ``cluster``); producers depend on it, not the
reverse. See ``docs/adr/0001-behavior-producer-agnostic-target.md``.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import h5py
import numpy as np

from maze.kpms.behavior_ethogram.paths import (
    behavior_bouts_csv,
    behavior_frames_h5,
    behavior_provenance_json,
)
from maze.kpms.io import write_json

SCHEMA_VERSION = "behavior_labeling_v1"

#: Sentinel behavior id for frames a producer left unlabeled / gap frames.
UNLABELED = -1

BEHAVIOR_BOUT_FIELDS = (
    "trial_key",
    "behavior_id",
    "behavior_name",
    "bout_index",
    "start_frame",
    "end_frame",
    "n_frames",
    "duration_s",
)


@dataclass(frozen=True, eq=False)
class TrialFrameLabels:
    """Per-frame Behavior labels for one trial on the source-video timeline.

    ``source_frame_index`` must be strictly increasing (the canonical join key
    against the anchor and held-out kinematics); it may have gaps where the
    producer's upstream preprocessing dropped frames.
    """

    trial_key: str
    source_frame_index: np.ndarray
    behavior_id: np.ndarray

    def __post_init__(self) -> None:
        sfi = np.asarray(self.source_frame_index, dtype=np.int64).ravel()
        bid = np.asarray(self.behavior_id, dtype=np.int32).ravel()
        if len(sfi) != len(bid):
            raise ValueError("source_frame_index and behavior_id must share length")
        if len(sfi) and np.any(np.diff(sfi) <= 0):
            raise ValueError("source_frame_index must be strictly increasing")
        object.__setattr__(self, "source_frame_index", sfi)
        object.__setattr__(self, "behavior_id", bid)

    def __len__(self) -> int:
        return int(len(self.source_frame_index))


@dataclass(frozen=True, eq=False)
class BehaviorLabeling:
    """A producer's complete frame-level Behavior labeling for a cohort."""

    producer: str
    fit_id: str
    fps: float
    trials: tuple[TrialFrameLabels, ...]
    behavior_names: Mapping[int, str] = field(default_factory=dict)
    params: Mapping[str, object] = field(default_factory=dict)
    input_hashes: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BehaviorBout:
    """One contiguous run of a single behavior id within a trial (RLE row)."""

    trial_key: str
    behavior_id: int
    behavior_name: str
    bout_index: int
    start_frame: int
    end_frame: int
    n_frames: int
    duration_s: float


def _runs(values: np.ndarray) -> list[tuple[int, int, int]]:
    """Return ``(value, start, end_exclusive)`` runs over a 1-D int array."""
    arr = np.asarray(values).ravel()
    n = len(arr)
    if n == 0:
        return []
    out: list[tuple[int, int, int]] = []
    i0 = 0
    cur = int(arr[0])
    for i in range(1, n):
        v = int(arr[i])
        if v != cur:
            out.append((cur, i0, i))
            i0 = i
            cur = v
    out.append((cur, i0, n))
    return out


def labeling_to_bouts(
    labeling: BehaviorLabeling,
    *,
    include_unlabeled: bool = False,
) -> list[BehaviorBout]:
    """Run-length encode per-frame labels into bout rows (source-frame bounds)."""
    fps = float(labeling.fps)
    out: list[BehaviorBout] = []
    for trial in labeling.trials:
        sfi = trial.source_frame_index
        bout_index = 0
        for val, lo, hi in _runs(trial.behavior_id):
            if not include_unlabeled and val == UNLABELED:
                continue
            n = int(hi - lo)
            out.append(
                BehaviorBout(
                    trial_key=trial.trial_key,
                    behavior_id=int(val),
                    behavior_name=str(labeling.behavior_names.get(int(val), "")),
                    bout_index=bout_index,
                    start_frame=int(sfi[lo]),
                    end_frame=int(sfi[hi - 1]),
                    n_frames=n,
                    duration_s=(float(n) / fps) if fps > 0 else 0.0,
                )
            )
            bout_index += 1
    return out


def hash_file(path: Path | str) -> str:
    """SHA-256 of a file, for producer provenance ``input_hashes``."""
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_frames_h5(path: Path, labeling: BehaviorLabeling) -> None:
    with h5py.File(path, "w") as f:
        f.attrs["schema"] = SCHEMA_VERSION
        f.attrs["producer"] = labeling.producer
        f.attrs["fit_id"] = labeling.fit_id
        f.attrs["fps"] = float(labeling.fps)
        trials_grp = f.create_group("trials")
        for i, trial in enumerate(labeling.trials):
            # Index-named groups avoid any trial_key/HDF5 charset issues and
            # preserve order; the real key lives in an attr.
            tg = trials_grp.create_group(f"t{i:06d}")
            tg.attrs["trial_key"] = trial.trial_key
            tg.create_dataset(
                "source_frame_index",
                data=trial.source_frame_index.astype(np.int64, copy=False),
                compression="gzip",
            )
            tg.create_dataset(
                "behavior_id",
                data=trial.behavior_id.astype(np.int32, copy=False),
                compression="gzip",
            )


def _read_frames_h5(path: Path) -> list[TrialFrameLabels]:
    trials: list[TrialFrameLabels] = []
    with h5py.File(path, "r") as f:
        trials_grp = f["trials"]
        for name in sorted(trials_grp.keys()):
            tg = trials_grp[name]
            trials.append(
                TrialFrameLabels(
                    trial_key=str(tg.attrs["trial_key"]),
                    source_frame_index=tg["source_frame_index"][()],
                    behavior_id=tg["behavior_id"][()],
                )
            )
    return trials


def _write_bouts_csv(path: Path, bouts: list[BehaviorBout]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(BEHAVIOR_BOUT_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for bout in bouts:
            writer.writerow(asdict(bout))


def _provenance_payload(labeling: BehaviorLabeling) -> dict:
    n_labeled = int(sum(int(np.sum(t.behavior_id != UNLABELED)) for t in labeling.trials))
    return {
        "schema": SCHEMA_VERSION,
        "producer": labeling.producer,
        "fit_id": labeling.fit_id,
        "fps": float(labeling.fps),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_trials": len(labeling.trials),
        "n_labeled_frames": n_labeled,
        "behavior_names": {str(k): str(v) for k, v in labeling.behavior_names.items()},
        "params": dict(labeling.params),
        "input_hashes": dict(labeling.input_hashes),
    }


def write_behavior_labeling(
    artifact_dir: Path | str,
    labeling: BehaviorLabeling,
    *,
    include_unlabeled_bouts: bool = False,
) -> None:
    """Write the three-file Behavior labeling artifact into ``artifact_dir``."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_frames_h5(behavior_frames_h5(artifact_dir), labeling)
    _write_bouts_csv(
        behavior_bouts_csv(artifact_dir),
        labeling_to_bouts(labeling, include_unlabeled=include_unlabeled_bouts),
    )
    write_json(behavior_provenance_json(artifact_dir), _provenance_payload(labeling))


def read_behavior_labeling(artifact_dir: Path | str) -> BehaviorLabeling:
    """Load a Behavior labeling artifact written by :func:`write_behavior_labeling`."""
    artifact_dir = Path(artifact_dir)
    with behavior_provenance_json(artifact_dir).open(encoding="utf-8") as f:
        prov = json.load(f)
    trials = _read_frames_h5(behavior_frames_h5(artifact_dir))
    behavior_names = {int(k): str(v) for k, v in prov.get("behavior_names", {}).items()}
    return BehaviorLabeling(
        producer=str(prov["producer"]),
        fit_id=str(prov["fit_id"]),
        fps=float(prov["fps"]),
        trials=tuple(trials),
        behavior_names=behavior_names,
        params=dict(prov.get("params", {})),
        input_hashes=dict(prov.get("input_hashes", {})),
    )


def read_behavior_bouts_csv(path: Path | str) -> list[BehaviorBout]:
    """Read back the derived bout CSV (mainly for tests / downstream joins)."""
    out: list[BehaviorBout] = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(
                BehaviorBout(
                    trial_key=str(row["trial_key"]),
                    behavior_id=int(row["behavior_id"]),
                    behavior_name=str(row["behavior_name"]),
                    bout_index=int(row["bout_index"]),
                    start_frame=int(row["start_frame"]),
                    end_frame=int(row["end_frame"]),
                    n_frames=int(row["n_frames"]),
                    duration_s=float(row["duration_s"]),
                )
            )
    return out
