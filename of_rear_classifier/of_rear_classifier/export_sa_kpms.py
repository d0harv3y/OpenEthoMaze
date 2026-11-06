"""Export SuperAnimal TVM H5 → keypoint-MoSeq-friendly arrays (one recording)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from of_rear_classifier.sa_kpms_skeleton import SA_KPMS_BODY_PARTS


def sa_h5_to_coordinates(
    h5_path: Path | str,
    *,
    individual: str = "animal0",
    body_parts: tuple[str, ...] = SA_KPMS_BODY_PARTS,
    likelihood_min: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    """Return ``coordinates (T,K,2)``, ``confidences (T,K)``, part names.

    Thin import: ``maze.pipeline.open_field.dlc_h5`` only.
    """
    from maze.pipeline.open_field.dlc_h5 import bodypart_xy_likelihood, read_pose_table

    df = read_pose_table(h5_path)
    xy_list = []
    conf_list = []
    for part in body_parts:
        xy, lik = bodypart_xy_likelihood(df, part, individual=individual)
        if likelihood_min > 0:
            bad = lik < likelihood_min
            xy = xy.copy()
            xy[bad] = np.nan
        xy_list.append(xy)
        conf_list.append(lik)
    coordinates = np.stack(xy_list, axis=1)  # (T, K, 2)
    confidences = np.stack(conf_list, axis=1)  # (T, K)
    return coordinates, confidences, body_parts


def write_recording_npz(
    out_path: Path | str,
    coordinates: np.ndarray,
    confidences: np.ndarray,
    body_parts: tuple[str, ...],
    *,
    recording_id: str,
) -> Path:
    """Write one ``.npz`` for a future kpMS / custom fit ingest."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        coordinates=coordinates.astype(np.float32),
        confidences=confidences.astype(np.float32),
        body_parts=np.asarray(body_parts),
        recording_id=np.asarray(recording_id),
    )
    return path
