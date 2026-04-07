"""
Median syllable trajectories for exemplar visualization (keypoint-moseq).

Unlike :func:`keypoint_moseq.util.get_typical_trajectories`, aggregation can omit
``inverse_rigid_transform`` (arena / world coordinates) so loops show translation.
"""

from __future__ import annotations

from typing import Any

import numpy as np

_KPMS_UTIL_ERROR: Exception | None = None
try:
    from keypoint_moseq.util import (
        get_instance_trajectories,
        get_syllable_instances,
        reindex_by_bodyparts,
        sample_instances,
    )

    _HAS_KPMS_UTIL = True
except Exception as e:  # pragma: no cover - optional dependency
    _HAS_KPMS_UTIL = False
    _KPMS_UTIL_ERROR = e


def typical_trajectories_for_exemplar_tray(
    coordinates: dict[str, Any],
    results: dict[str, Any],
    *,
    pre: int,
    post: int,
    min_frequency: float,
    min_duration: int,
    bodyparts: list[str] | None,
    use_bodyparts: list[str] | None,
    density_sample: bool,
    sampling_options: dict[str, Any],
    egocentric: bool,
) -> dict[int, np.ndarray]:
    """
    Like ``keypoint_moseq.util.get_typical_trajectories``, but the median trajectory
    can be built in **arena** coordinates (``egocentric=False``) so the tray shows
    translation through space. Density sampling still uses ego-centric windows for
    PCA when ``density_sample=True``, matching kpMS instance choice.
    """
    if not _HAS_KPMS_UTIL:
        raise RuntimeError(
            "keypoint-moseq is required for exemplar trajectories. Install with: uv sync --extra kpms"
        ) from _KPMS_UTIL_ERROR

    if bodyparts is not None and use_bodyparts is not None:
        coordinates = reindex_by_bodyparts(coordinates, bodyparts, use_bodyparts)

    syllables = {k: v["syllable"] for k, v in results.items()}
    centroids = {k: v["centroid"] for k, v in results.items()}
    headings = {k: v["heading"] for k, v in results.items()}

    n_neighbors = int(sampling_options["n_neighbors"])
    min_instances = n_neighbors if density_sample else 1
    syllable_instances = get_syllable_instances(
        syllables,
        pre=pre,
        post=post,
        min_duration=min_duration,
        min_frequency=min_frequency,
        min_instances=min_instances,
    )

    if len(syllable_instances) == 0:
        raise ValueError(
            "No syllables with sufficient instances to generate a trajectory. "
            "Try lowering min_frequency or min_duration, or check syllable diversity."
        )

    if density_sample:
        so = dict(sampling_options)
        so["mode"] = "density"
        sampled_instances = sample_instances(
            syllable_instances,
            n_neighbors,
            coordinates=coordinates,
            centroids=centroids,
            headings=headings,
            pre=pre,
            post=post,
            **so,
        )
    else:
        sampled_instances = syllable_instances

    if egocentric:
        traj_kw: dict[str, Any] = {"centroids": centroids, "headings": headings}
    else:
        traj_kw = {"centroids": None, "headings": None}

    trajectories = {
        syllable: get_instance_trajectories(
            instances,
            coordinates,
            pre=pre,
            post=post,
            **traj_kw,
        )
        for syllable, instances in sampled_instances.items()
    }

    return {int(s): np.nanmedian(ts, axis=0) for s, ts in trajectories.items()}
