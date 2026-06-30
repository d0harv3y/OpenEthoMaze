"""Load independent legacy-VAST speed for the is_moving anchor (ADR-0002)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np

from maze.core.h5_layout import resolve_ambulation_metrics_group
from maze.core.schema import XY_ROW_DTYPE
from maze.kpms.behavior_ethogram.anchor import speed_mps_from_xy_px
from maze.kpms.frame_alignment import kpms_recording_key
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest

_LEGACY_POINTS = ("spot_hybrid", "center", "spot", "centroid")


@dataclass(frozen=True)
class TrialLegacySpeed:
    """Per-frame legacy ambulation on the source-video timeline."""

    trial_key: str
    source_frame_index: np.ndarray
    speed_mps: np.ndarray
    valid: np.ndarray
    trial_state: np.ndarray

    def __post_init__(self) -> None:
        sfi = np.asarray(self.source_frame_index, dtype=np.int64).ravel()
        speed = np.asarray(self.speed_mps, dtype=np.float64).ravel()
        valid = np.asarray(self.valid, dtype=bool).ravel()
        ts = np.asarray(self.trial_state)
        n = len(sfi)
        if not (len(speed) == len(valid) == len(ts) == n):
            raise ValueError("legacy speed arrays must share length")
        object.__setattr__(self, "source_frame_index", sfi)
        object.__setattr__(self, "speed_mps", speed)
        object.__setattr__(self, "valid", valid)
        object.__setattr__(self, "trial_state", ts)


def _decode_state(value: object) -> str:
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _read_xy_table(g_trial: h5py.Group, point: str) -> np.ndarray | None:
    g_amb = resolve_ambulation_metrics_group(g_trial)
    if g_amb is None or point not in g_amb or "xy" not in g_amb[point]:
        return None
    rec = g_amb[point]["xy"][()]
    if rec.dtype != XY_ROW_DTYPE:
        return None
    return rec


def load_legacy_vast_speed(
    legacy_db: Path | str,
    manifest: TrialManifest,
    *,
    point: str | None = None,
) -> TrialLegacySpeed | None:
    """Read spot_hybrid (or fallback) XY and derive per-frame speed from trial attrs."""
    legacy_db = Path(legacy_db)
    key = TrialKey.from_manifest(manifest)
    with h5py.File(legacy_db, "r") as h5:
        gpath = key.path().lstrip("/")
        if gpath not in h5:
            return None
        g = h5[gpath]
        fps = float(g.attrs.get("fps") or g.attrs.get("h5_fps") or 30.0)
        px_per_cm = float(g.attrs.get("px_per_cm") or 0.0)
        if px_per_cm <= 0:
            return None

        points = (point,) if point else _LEGACY_POINTS
        rec = None
        point_used = None
        for pt in points:
            rec = _read_xy_table(g, pt)
            if rec is not None:
                point_used = pt
                break
        if rec is None or point_used is None:
            return None

        names = rec.dtype.names or ()
        if "frame_index" in names:
            sfi = np.asarray(rec["frame_index"], dtype=np.int64)
        else:
            sfi = np.arange(len(rec), dtype=np.int64)
        xy = np.column_stack((rec["x"].astype(np.float64), rec["y"].astype(np.float64)))
        valid = np.asarray(rec["valid"], dtype=bool) & np.isfinite(xy).all(axis=1)
        speed = speed_mps_from_xy_px(xy, fps=fps, px_per_cm=px_per_cm)
        if "trial_state" in names:
            states = np.array([_decode_state(s) for s in rec["trial_state"]], dtype=object)
        else:
            states = np.array(["run"] * len(rec), dtype=object)

        return TrialLegacySpeed(
            trial_key=kpms_recording_key(manifest),
            source_frame_index=sfi,
            speed_mps=speed,
            valid=valid,
            trial_state=states,
        )


def run_phase_mask(trial_state: np.ndarray) -> np.ndarray:
    """Boolean mask for ``trial_state == 'run'``."""
    return np.array([_decode_state(s).strip().lower() == "run" for s in trial_state], dtype=bool)
