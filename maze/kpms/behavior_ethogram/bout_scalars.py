"""Pure bout scalar statistics (no H5 / GPU).

Feature names and CSV columns: ``bout_feature_contract.py``;
see ``docs/bout_feature_contract.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .bout_feature_contract import (
    CLUSTERING_FEATURE_NAMES,
    OPTIONAL_HEADING_FEATURE_NAMES,
)

DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS = 0.08


def syllable_runs(z: np.ndarray) -> list[tuple[int, int, int]]:
    """Return ``(syllable_id, start, end_exclusive)`` runs along kpMS rows."""
    arr = np.asarray(z, dtype=np.int64).ravel()
    n = len(arr)
    if n == 0:
        return []
    boundaries = np.flatnonzero(np.diff(arr)) + 1
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [n]))
    ids = arr[starts]
    return [(int(ids[i]), int(starts[i]), int(ends[i])) for i in range(len(starts))]


def _finite(values: Sequence[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64).ravel()
    return arr[np.isfinite(arr)]


def bout_iqr(values: Sequence[float] | np.ndarray) -> float:
    arr = _finite(values)
    if arr.size == 0:
        return float("nan")
    q75, q25 = np.percentile(arr, [75, 25])
    return float(q75 - q25)


def mean_abs_dheading(heading_rad: Sequence[float] | np.ndarray) -> float:
    arr = _finite(heading_rad)
    if arr.size < 2:
        return 0.0
    delta = np.abs(np.diff(np.unwrap(arr)))
    return float(np.mean(delta))


def bout_net_dheading_rad(heading_rad: Sequence[float] | np.ndarray) -> float:
    """Signed net heading change across a bout (radians, unwrapped)."""
    arr = _finite(heading_rad)
    if arr.size < 2:
        return 0.0
    unwrapped = np.unwrap(arr)
    return float(unwrapped[-1] - unwrapped[0])


def bout_straightness(centroid_xy_px: Sequence[Sequence[float]] | np.ndarray) -> float:
    """Net displacement over path length, clipped to [0, 1]."""
    xy = np.asarray(centroid_xy_px, dtype=np.float64)
    if xy.ndim != 2 or xy.shape[0] < 2:
        return 0.0
    net = float(np.linalg.norm(xy[-1] - xy[0]))
    path = float(np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1)))
    if path <= 0:
        return 0.0
    return float(np.clip(net / path, 0.0, 1.0))


def circular_mean_sin_cos(heading_rad: Sequence[float] | np.ndarray) -> tuple[float, float]:
    arr = _finite(heading_rad)
    if arr.size == 0:
        return (float("nan"), float("nan"))
    return (float(np.mean(np.sin(arr))), float(np.mean(np.cos(arr))))


def circular_mean_heading(heading_rad: Sequence[float] | np.ndarray) -> float:
    sin_m, cos_m = circular_mean_sin_cos(heading_rad)
    if not np.isfinite(sin_m):
        return float("nan")
    return float(np.arctan2(sin_m, cos_m))


def circular_iqr_heading(heading_rad: Sequence[float] | np.ndarray) -> float:
    arr = _finite(heading_rad)
    if arr.size == 0:
        return float("nan")
    # Wrap to circular mean reference for IQR on a line.
    mu = circular_mean_heading(arr)
    rel = np.angle(np.exp(1j * (arr - mu)))
    q75, q25 = np.percentile(rel, [75, 25])
    return float(q75 - q25)


def bout_ambiguous(
    speed_iqr_mps: float,
    *,
    threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
) -> bool:
    if not np.isfinite(speed_iqr_mps):
        return False
    return float(speed_iqr_mps) > float(threshold_mps)


@dataclass(frozen=True)
class BoutScalarFeatures:
    raw_syllable_id: int
    bout_index: int
    row_start: int
    row_end_exclusive: int
    bout_frames: int
    bout_duration_s: float
    bout_mean_speed_mps: float
    bout_mean_abs_dheading: float
    bout_mean_blob_area_px2: float
    bout_iqr_speed_mps: float
    bout_iqr_abs_dheading: float
    bout_iqr_blob_area_px2: float
    bout_mean_heading_rad: float | None = None
    bout_mean_heading_sin: float | None = None
    bout_mean_heading_cos: float | None = None
    bout_iqr_heading_rad: float | None = None
    bout_net_dheading_rad: float = 0.0
    bout_straightness: float = 0.0
    bout_primary_state: str = ""
    ambiguous: bool = False


def aggregate_bout_scalars(
    *,
    syllable_id: int,
    bout_index: int,
    row_start: int,
    row_end_exclusive: int,
    speed_mps: Sequence[float],
    abs_dheading: Sequence[float],
    blob_area_px2: Sequence[float],
    heading_rad: Sequence[float] | None,
    centroid_xy_px: Sequence[Sequence[float]] | np.ndarray | None = None,
    fps: float,
    trial_states: Sequence[str] | None = None,
    ambiguous_threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
    include_heading_direction: bool = False,
) -> BoutScalarFeatures:
    lo, hi = row_start, row_end_exclusive
    speed_slice = speed_mps[lo:hi]
    dheading_slice = abs_dheading[lo:hi]
    area_slice = blob_area_px2[lo:hi]
    n_frames = hi - lo
    duration_s = float(n_frames) / float(fps) if fps > 0 else 0.0

    speed_iqr = bout_iqr(speed_slice)
    primary_state = ""
    if trial_states is not None and n_frames > 0:
        states = [str(s).strip().lower() for s in trial_states[lo:hi]]
        if states:
            primary_state = max(set(states), key=states.count)

    mean_heading: float | None = None
    iqr_heading: float | None = None
    mean_sin: float | None = None
    mean_cos: float | None = None
    net_dheading = 0.0
    straightness = 0.0
    if heading_rad is not None:
        h_slice = heading_rad[lo:hi]
        net_dheading = bout_net_dheading_rad(h_slice)
        if include_heading_direction:
            mean_heading = circular_mean_heading(h_slice)
            iqr_heading = circular_iqr_heading(h_slice)
            mean_sin, mean_cos = circular_mean_sin_cos(h_slice)
    if centroid_xy_px is not None:
        straightness = bout_straightness(np.asarray(centroid_xy_px, dtype=np.float64)[lo:hi])

    return BoutScalarFeatures(
        raw_syllable_id=int(syllable_id),
        bout_index=int(bout_index),
        row_start=int(row_start),
        row_end_exclusive=int(hi),
        bout_frames=int(n_frames),
        bout_duration_s=duration_s,
        bout_mean_speed_mps=float(np.nanmean(_finite(speed_slice))) if n_frames else 0.0,
        bout_mean_abs_dheading=float(np.nanmean(_finite(dheading_slice))) if n_frames else 0.0,
        bout_mean_blob_area_px2=float(np.nanmean(_finite(area_slice))) if n_frames else 0.0,
        bout_iqr_speed_mps=speed_iqr,
        bout_iqr_abs_dheading=bout_iqr(dheading_slice),
        bout_iqr_blob_area_px2=bout_iqr(area_slice),
        bout_mean_heading_rad=mean_heading,
        bout_mean_heading_sin=mean_sin,
        bout_mean_heading_cos=mean_cos,
        bout_iqr_heading_rad=iqr_heading,
        bout_net_dheading_rad=net_dheading,
        bout_straightness=straightness,
        bout_primary_state=primary_state,
        ambiguous=bout_ambiguous(speed_iqr, threshold_mps=ambiguous_threshold_mps),
    )


def compile_trial_bout_features(
    z: np.ndarray,
    *,
    speed_mps: np.ndarray,
    abs_dheading: np.ndarray,
    blob_area_px2: np.ndarray,
    heading_rad: np.ndarray | None,
    centroid_xy_px: np.ndarray | None = None,
    fps: float,
    trial_states: Sequence[str] | None = None,
    include_heading_direction: bool = False,
) -> list[BoutScalarFeatures]:
    """Collapse syllable runs to bout scalar rows."""
    if not (
        len(z) == len(speed_mps) == len(abs_dheading) == len(blob_area_px2)
    ):
        raise ValueError("z and kinematic arrays must share length")
    if heading_rad is not None and len(heading_rad) != len(z):
        raise ValueError("heading_rad length must match z")
    if centroid_xy_px is not None and len(centroid_xy_px) != len(z):
        raise ValueError("centroid_xy_px length must match z")
    out: list[BoutScalarFeatures] = []
    for bout_index, (sid, lo, hi) in enumerate(syllable_runs(z)):
        out.append(
            aggregate_bout_scalars(
                syllable_id=sid,
                bout_index=bout_index,
                row_start=lo,
                row_end_exclusive=hi,
                speed_mps=speed_mps,
                abs_dheading=abs_dheading,
                blob_area_px2=blob_area_px2,
                heading_rad=heading_rad,
                centroid_xy_px=centroid_xy_px,
                fps=fps,
                trial_states=trial_states,
                include_heading_direction=include_heading_direction,
            )
        )
    return out


def feature_matrix_for_clustering(
    rows: Sequence[BoutScalarFeatures],
    *,
    include_heading_direction: bool = False,
) -> tuple[np.ndarray, list[str]]:
    """Z-scoring happens in the cluster module; return raw feature matrix + names."""
    names = list(CLUSTERING_FEATURE_NAMES)
    if include_heading_direction:
        names.extend(OPTIONAL_HEADING_FEATURE_NAMES)

    mat = np.empty((len(rows), len(names)), dtype=np.float64)
    for i, row in enumerate(rows):
        vals = [
            row.bout_mean_speed_mps,
            row.bout_mean_abs_dheading,
            row.bout_mean_blob_area_px2,
            row.bout_iqr_speed_mps,
            row.bout_iqr_abs_dheading,
            row.bout_iqr_blob_area_px2,
            row.bout_duration_s,
            row.bout_net_dheading_rad,
            row.bout_straightness,
        ]
        if include_heading_direction:
            vals.extend(
                [
                    row.bout_mean_heading_sin if row.bout_mean_heading_sin is not None else 0.0,
                    row.bout_mean_heading_cos if row.bout_mean_heading_cos is not None else 0.0,
                ]
            )
        mat[i, :] = vals
    return mat, names


def feature_matrix_for_arhmm(
    rows: Sequence[BoutScalarFeatures],
    *,
    include_heading_direction: bool = False,
    append_columns: np.ndarray | None = None,
    append_names: Sequence[str] | None = None,
    include_cluster_feature: bool = False,
    cluster_ids: Sequence[int] | None = None,
) -> tuple[np.ndarray, list[str]]:
    if include_cluster_feature:
        raise ValueError(
            "include_cluster_feature is removed in S2; use syllable kinematic signatures instead"
        )
    if cluster_ids is not None:
        raise ValueError("cluster_ids are not valid AR-HMM features in S2")
    mat, names = feature_matrix_for_clustering(
        rows, include_heading_direction=include_heading_direction
    )
    if append_columns is not None:
        if append_columns.shape[0] != len(rows):
            raise ValueError("append_columns row count must match rows")
        mat = np.concatenate([mat, append_columns], axis=1)
        if append_names is None:
            raise ValueError("append_names required when append_columns is set")
        names = [*names, *list(append_names)]
    return mat, names
