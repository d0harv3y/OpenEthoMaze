"""Anterior/posterior keypoint indices for kpMS fit and apply."""

from __future__ import annotations

from typing import Literal

from maze.pipeline.blob_orient import blob_anterior_posterior_idxs

PoseStream = Literal["anatomical", "blob", "fused"]


def anterior_posterior_idxs(
    bodyparts: list[str] | tuple[str, ...],
    pose_stream: PoseStream = "anatomical",
) -> tuple[list[int], list[int]]:
    """
    Return ``(anterior_idxs, posterior_idxs)`` for keypoint-MoSeq heading alignment.

    Stream A uses anatomical ``nose`` / ``tail``. Stream B uses motion-oriented
    ``blob_p0`` / opposite vertex (see :func:`blob_anterior_posterior_idxs`).
    """
    if pose_stream == "blob":
        return blob_anterior_posterior_idxs(len(bodyparts))
    if pose_stream == "fused":
        raise NotImplementedError("pose_stream='fused' is T4b; use anatomical or blob")

    bp = list(bodyparts)
    try:
        anterior = [bp.index("nose")]
    except ValueError:
        anterior = [0]
    try:
        posterior = [bp.index("tail")]
    except ValueError:
        posterior = [1] if len(bp) > 1 else [0]
    return anterior, posterior
