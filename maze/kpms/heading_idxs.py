"""Anterior/posterior keypoint indices for kpMS fit and apply."""

from __future__ import annotations

from typing import Literal

from maze.core.anatomy import BLOB_NODE_NAMES, STANDARD_NODE_NAMES
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

    bp = list(bodyparts)
    if pose_stream == "fused":
        blob_ant, blob_post = blob_anterior_posterior_idxs(len(BLOB_NODE_NAMES))
        offset = len(STANDARD_NODE_NAMES)

        def _idx(name: str, fallback: int) -> int:
            try:
                return bp.index(name)
            except ValueError:
                return fallback

        anterior = [
            _idx("nose", 0),
            _idx(BLOB_NODE_NAMES[blob_ant[0]], offset + blob_ant[0]),
        ]
        posterior = [
            _idx("tail", 1 if len(bp) > 1 else 0),
            _idx(BLOB_NODE_NAMES[blob_post[0]], offset + blob_post[0]),
        ]
        return anterior, posterior

    try:
        anterior = [bp.index("nose")]
    except ValueError:
        anterior = [0]
    try:
        posterior = [bp.index("tail")]
    except ValueError:
        posterior = [1] if len(bp) > 1 else [0]
    return anterior, posterior
