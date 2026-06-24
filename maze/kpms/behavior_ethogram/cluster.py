"""Cohort HDBSCAN on bout scalar features."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .bout_scalars import BoutScalarFeatures, feature_matrix_for_clustering


@dataclass(frozen=True)
class HdbscanClusterResult:
    labels: np.ndarray
    feature_names: tuple[str, ...]
    n_features: int
    n_bouts: int
    n_clusters: int
    n_noise: int


def zscore_features(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mat = np.asarray(matrix, dtype=np.float64)
    mean = np.nanmean(mat, axis=0)
    std = np.nanstd(mat, axis=0)
    std = np.where(std < 1e-12, 1.0, std)
    z = (mat - mean) / std
    z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
    return z, mean, std


def cluster_bout_features_hdbscan(
    rows: Sequence[BoutScalarFeatures],
    *,
    include_heading_direction: bool = False,
    min_cluster_size: int = 15,
    min_samples: int = 5,
) -> HdbscanClusterResult:
    import hdbscan

    mat, names = feature_matrix_for_clustering(
        rows, include_heading_direction=include_heading_direction
    )
    z, _, _ = zscore_features(mat)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=int(min_cluster_size),
        min_samples=int(min_samples),
        metric="euclidean",
    )
    labels = clusterer.fit_predict(z)
    labels = np.asarray(labels, dtype=np.int64)
    n_clusters = len({int(x) for x in labels.tolist() if int(x) >= 0})
    n_noise = int(np.sum(labels < 0))
    return HdbscanClusterResult(
        labels=labels,
        feature_names=tuple(names),
        n_features=len(names),
        n_bouts=len(rows),
        n_clusters=n_clusters,
        n_noise=n_noise,
    )
