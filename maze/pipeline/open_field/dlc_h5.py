"""Read a SuperAnimal / DeepLabCut multi-animal pose HDF5 (pandas table)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

MOUSE_CENTER = "mouse_center"


def read_pose_table(h5_path: Path | str) -> pd.DataFrame:
    """Load ``df_with_missing`` from a SuperAnimal video HDF5."""
    path = Path(h5_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_hdf(path)


def bodypart_xy_likelihood(
    df: pd.DataFrame,
    bodypart: str,
    *,
    individual: str = "animal0",
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``xy`` shape ``(T, 2)`` and ``likelihood`` shape ``(T,)`` for one part."""
    try:
        block = df.xs(individual, level="individuals", axis=1).xs(bodypart, level="bodyparts", axis=1)
    except KeyError as exc:
        raise KeyError(f"{bodypart!r} / {individual!r} not in pose table") from exc
    x = block.xs("x", level="coords", axis=1).to_numpy(dtype=np.float64).reshape(-1)
    y = block.xs("y", level="coords", axis=1).to_numpy(dtype=np.float64).reshape(-1)
    lik = block.xs("likelihood", level="coords", axis=1).to_numpy(dtype=np.float64).reshape(-1)
    return np.column_stack([x, y]), lik


def list_bodyparts(df: pd.DataFrame) -> list[str]:
    return list(df.columns.get_level_values("bodyparts").unique())
