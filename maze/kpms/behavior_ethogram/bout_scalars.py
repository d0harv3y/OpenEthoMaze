"""Pure bout scalar statistics (no H5 / GPU)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS = 0.08


def syllable_runs(z: np.ndarray) -> list[tuple[int, int, int]]:
    """Return ``(syllable_id, start, end_exclusive)`` runs along kpMS rows."""
    arr = np.asarray(z, dtype=np.int64).ravel()
    n = len(arr)
    if n == 0:
        return []
    out: list[tuple[int, int, int]] = []
    i0 = 0
    cur = int(arr[0])
    for i in range(1, n):
        if int(arr[i]) != cur:
            out.append((cur, i0, i))
            i0 = i
            cur = int(arr[i])
    out.append((cur, i0, n))
    return out


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


def circular_mean_heading(heading_rad: Sequence[float] | np.ndarray) -> float:
    arr = _finite(heading_rad)
    if arr.size == 0:
        return float("nan")
    return float(np.arctan2(np.mean(np.sin(arr)), np.mean(np.cos(arr))))


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
    bout_iqr_heading_rad: float | None = None
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
    if include_heading_direction and heading_rad is not None:
        h_slice = heading_rad[lo:hi]
        mean_heading = circular_mean_heading(h_slice)
        iqr_heading = circular_iqr_heading(h_slice)

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
        bout_iqr_heading_rad=iqr_heading,
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
    names = [
        "bout_mean_speed_mps",
        "bout_mean_abs_dheading",
        "bout_mean_blob_area_px2",
        "bout_iqr_speed_mps",
        "bout_iqr_abs_dheading",
        "bout_iqr_blob_area_px2",
        "bout_duration_s",
    ]
    if include_heading_direction:
        names.extend(["bout_mean_heading_rad", "bout_iqr_heading_rad"])

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
        ]
        if include_heading_direction:
            vals.extend(
                [
                    row.bout_mean_heading_rad if row.bout_mean_heading_rad is not None else 0.0,
                    row.bout_iqr_heading_rad if row.bout_iqr_heading_rad is not None else 0.0,
                ]
            )
        mat[i, :] = vals
    return mat, names


def feature_matrix_for_arhmm(
    rows: Sequence[BoutScalarFeatures],
    *,
    include_heading_direction: bool = False,
    include_cluster_feature: bool = False,
    cluster_ids: Sequence[int] | None = None,
) -> tuple[np.ndarray, list[str]]:
    mat, names = feature_matrix_for_clustering(
        rows, include_heading_direction=include_heading_direction
    )
    if include_cluster_feature:
        if cluster_ids is None or len(cluster_ids) != len(rows):
            raise ValueError("cluster_ids required when include_cluster_feature=True")
        cid = np.asarray(cluster_ids, dtype=np.float64).reshape(-1, 1)
        mat = np.concatenate([mat, cid], axis=1)
        names = [*names, "cluster_id"]
    return mat, names
