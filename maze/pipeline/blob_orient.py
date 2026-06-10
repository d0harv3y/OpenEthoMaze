"""
Motion-oriented resampling of backup-tracker blob contours to fixed pseudo-keypoints.

Converts a binary ``blob_mask`` or closed contour into ``BLOB_VERTEX_COUNT`` vertices
(``blob_p0`` … ``blob_p7``) with order anchored to centroid velocity. Temporal
unwrap keeps vertex indices stable across frames.

When speed is below ``speed_epsilon_px``, ``heading_rad`` is ``NaN`` and frame
``score`` is reduced. An optional anatomical **heading hint** (neck→nose vector
from a SLEAP frame) disambiguates orientation when velocity is unreliable; the
hint affects rotation only — anatomical node names are never written into
``BLOB_NODE_NAMES``.

See ``docs/h5_tracking_contract.md`` and ``docs/ethogram_scope.md`` E6 stream B.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from maze.core.anatomy import BLOB_VERTEX_COUNT

DEFAULT_SPEED_EPSILON_PX = 1.0
DEFAULT_MIN_AREA_PX = 40.0


@dataclass(frozen=True)
class BlobOrientFrame:
    """One frame of motion-oriented blob polygon output."""

    xy: np.ndarray
    heading_rad: float
    score: float
    valid: bool
    centroid: np.ndarray


@dataclass
class BlobOrientState:
    """Cross-frame memory for velocity heading and temporal unwrap."""

    prev_centroid: np.ndarray | None = None
    prev_vertices: np.ndarray | None = None


@dataclass
class BlobOrientTracker:
    """
    Stateful converter: contour or mask → oriented ``BLOB_VERTEX_COUNT``-gon per frame.

    Reuse one tracker instance for the duration of a trial so temporal unwrap and
    velocity heading remain consistent.
    """

    speed_epsilon_px: float = DEFAULT_SPEED_EPSILON_PX
    min_area_px: float = DEFAULT_MIN_AREA_PX
    _state: BlobOrientState = field(default_factory=BlobOrientState, init=False, repr=False)

    def reset(self) -> None:
        """Clear temporal state (trial boundary, seek, or tracker re-init)."""
        self._state = BlobOrientState()

    def process_mask(
        self,
        mask: np.ndarray,
        *,
        anatomical_pose_xy: np.ndarray | None = None,
        anatomical_node_names: tuple[str, ...] | list[str] | None = None,
    ) -> BlobOrientFrame:
        """Extract the largest boundary contour from ``mask`` and orient it."""
        contour = contour_from_mask(mask)
        if contour is None:
            return self._invalid_frame()
        return self.process_contour(
            contour,
            anatomical_pose_xy=anatomical_pose_xy,
            anatomical_node_names=anatomical_node_names,
        )

    def process_contour(
        self,
        contour: np.ndarray,
        *,
        anatomical_pose_xy: np.ndarray | None = None,
        anatomical_node_names: tuple[str, ...] | list[str] | None = None,
    ) -> BlobOrientFrame:
        """Resample ``contour`` to eight vertices with motion-consistent order."""
        resampled = resample_contour(contour, BLOB_VERTEX_COUNT)
        if not np.isfinite(resampled).all():
            return self._invalid_frame()

        centroid = polygon_centroid(resampled)
        area = polygon_area(resampled)
        if area < self.min_area_px:
            return self._invalid_frame(centroid=centroid)

        heading, speed = velocity_heading(
            self._state.prev_centroid,
            centroid,
            speed_epsilon_px=self.speed_epsilon_px,
        )
        hint = anatomical_heading_hint(anatomical_pose_xy, anatomical_node_names)
        orient_heading = heading
        heading_from_motion = np.isfinite(heading)
        if not heading_from_motion and hint is not None:
            orient_heading = hint

        if orient_heading is None or not np.isfinite(orient_heading):
            oriented = resampled
        else:
            oriented = orient_vertices_by_heading(resampled, centroid, orient_heading)

        if self._state.prev_vertices is not None:
            oriented = temporal_unwrap(oriented, self._state.prev_vertices)

        score = frame_quality_score(
            area=area,
            speed=speed,
            speed_epsilon_px=self.speed_epsilon_px,
            heading_from_motion=heading_from_motion,
            has_anatomical_hint=hint is not None,
            min_area_px=self.min_area_px,
        )

        out_heading = heading if heading_from_motion else float("nan")
        self._state.prev_centroid = centroid.copy()
        self._state.prev_vertices = oriented.copy()

        return BlobOrientFrame(
            xy=np.asarray(oriented, dtype=np.float32),
            heading_rad=float(out_heading),
            score=float(score),
            valid=True,
            centroid=np.asarray(centroid, dtype=np.float64),
        )

    def _invalid_frame(self, centroid: np.ndarray | None = None) -> BlobOrientFrame:
        c = (
            np.asarray(centroid, dtype=np.float64)
            if centroid is not None
            else (
                self._state.prev_centroid.copy()
                if self._state.prev_centroid is not None
                else np.array([np.nan, np.nan], dtype=np.float64)
            )
        )
        return BlobOrientFrame(
            xy=np.full((BLOB_VERTEX_COUNT, 2), np.nan, dtype=np.float32),
            heading_rad=float("nan"),
            score=0.0,
            valid=False,
            centroid=c,
        )


def contour_from_mask(mask: np.ndarray) -> np.ndarray | None:
    """
    Return boundary pixels of the foreground region as a closed contour ``(M, 2)`` xy.

    Points are ordered counterclockwise around the region centroid. Uses NumPy only
    (no OpenCV) so kpMS and pipeline tests stay lightweight.
    """
    fg = np.asarray(mask) > 0
    if not np.any(fg):
        return None

    padded = np.pad(fg, 1, mode="constant", constant_values=False)
    inner = padded[1:-1, 1:-1]
    boundary = inner & (
        ~padded[:-2, 1:-1] | ~padded[2:, 1:-1] | ~padded[1:-1, :-2] | ~padded[1:-1, 2:]
    )
    ys, xs = np.where(boundary)
    if xs.size == 0:
        return None

    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    centroid = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1] - centroid[1], pts[:, 0] - centroid[0])
    return pts[np.argsort(angles)]


def resample_contour(contour: np.ndarray, n_vertices: int) -> np.ndarray:
    """Evenly resample a closed contour to ``n_vertices`` points by arc length."""
    pts = np.asarray(contour, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 2 or pts.shape[0] < 3 or n_vertices <= 0:
        return np.full((max(n_vertices, 0), 2), np.nan)

    closed = np.vstack([pts, pts[0:1]])
    seg_len = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    total = float(np.sum(seg_len))
    if total <= 0.0:
        return np.full((n_vertices, 2), np.nan)

    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    targets = np.linspace(0.0, total, n_vertices, endpoint=False)
    out = np.empty((n_vertices, 2), dtype=np.float64)
    for i, target in enumerate(targets):
        idx = int(np.searchsorted(cum, target, side="right") - 1)
        idx = min(max(idx, 0), len(seg_len) - 1)
        seg_start = cum[idx]
        seg_end = cum[idx + 1]
        if seg_end <= seg_start:
            out[i] = closed[idx]
        else:
            t = (target - seg_start) / (seg_end - seg_start)
            out[i] = (1.0 - t) * closed[idx] + t * closed[idx + 1]
    return out


def polygon_centroid(vertices: np.ndarray) -> np.ndarray:
    """Area-weighted centroid of a simple polygon."""
    v = np.asarray(vertices, dtype=np.float64)
    x = v[:, 0]
    y = v[:, 1]
    x1 = np.roll(x, -1)
    y1 = np.roll(y, -1)
    cross = x * y1 - x1 * y
    area2 = float(np.sum(cross))
    if abs(area2) < 1e-9:
        return v.mean(axis=0)
    cx = float(np.sum((x + x1) * cross) / (3.0 * area2))
    cy = float(np.sum((y + y1) * cross) / (3.0 * area2))
    return np.array([cx, cy], dtype=np.float64)


def polygon_area(vertices: np.ndarray) -> float:
    """Absolute area of a simple polygon."""
    v = np.asarray(vertices, dtype=np.float64)
    x = v[:, 0]
    y = v[:, 1]
    return float(abs(0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)))


def velocity_heading(
    prev_centroid: np.ndarray | None,
    curr_centroid: np.ndarray,
    *,
    speed_epsilon_px: float,
) -> tuple[float, float]:
    """
    Return ``(heading_rad, speed_px)`` from consecutive centroids.

    ``heading_rad`` is ``NaN`` when ``speed_px < speed_epsilon_px``.
    """
    if prev_centroid is None or not np.isfinite(prev_centroid).all():
        return float("nan"), 0.0
    delta = np.asarray(curr_centroid, dtype=np.float64) - np.asarray(prev_centroid, dtype=np.float64)
    speed = float(np.linalg.norm(delta))
    if speed < speed_epsilon_px:
        return float("nan"), speed
    return float(np.arctan2(delta[1], delta[0])), speed


def anatomical_heading_hint(
    pose_xy: np.ndarray | None,
    node_names: tuple[str, ...] | list[str] | None,
) -> float | None:
    """
    Optional neck→nose heading (radians) for orientation when velocity is unreliable.

    Returns ``None`` when either landmark is missing or non-finite. Used only to
    pick the cyclic rotation of blob vertices; output names remain ``blob_p*``.
    """
    if pose_xy is None or node_names is None:
        return None
    xy = np.asarray(pose_xy, dtype=np.float64)
    if xy.ndim != 2 or xy.shape[1] != 2:
        return None

    name_to_idx = {str(name): i for i, name in enumerate(node_names)}
    if "neck" not in name_to_idx or "nose" not in name_to_idx:
        return None

    neck = xy[name_to_idx["neck"]]
    nose = xy[name_to_idx["nose"]]
    if not np.isfinite(neck).all() or not np.isfinite(nose).all():
        return None

    delta = nose - neck
    if float(np.linalg.norm(delta)) < 1e-6:
        return None
    return float(np.arctan2(delta[1], delta[0]))


def orient_vertices_by_heading(
    vertices: np.ndarray,
    centroid: np.ndarray,
    heading_rad: float,
) -> np.ndarray:
    """Rotate vertex order so ``blob_p0`` is closest to ``heading_rad`` from ``centroid``."""
    v = np.asarray(vertices, dtype=np.float64)
    rel = v - np.asarray(centroid, dtype=np.float64)
    angles = np.arctan2(rel[:, 1], rel[:, 0])
    delta = np.arctan2(np.sin(angles - heading_rad), np.cos(angles - heading_rad))
    front_idx = int(np.argmin(np.abs(delta)))
    return np.roll(v, -front_idx, axis=0)


def temporal_unwrap(current: np.ndarray, previous: np.ndarray) -> np.ndarray:
    """Cyclic-shift ``current`` to minimize L2 distance vs ``previous`` vertex order."""
    cur = np.asarray(current, dtype=np.float64)
    prev = np.asarray(previous, dtype=np.float64)
    if cur.shape != prev.shape or not np.isfinite(prev).all():
        return cur

    n = cur.shape[0]
    best = cur
    best_dist = float("inf")
    for k in range(n):
        rolled = np.roll(cur, -k, axis=0)
        dist = float(np.linalg.norm(rolled - prev))
        if dist < best_dist:
            best_dist = dist
            best = rolled
    return best


def frame_quality_score(
    *,
    area: float,
    speed: float,
    speed_epsilon_px: float,
    heading_from_motion: bool,
    has_anatomical_hint: bool,
    min_area_px: float = DEFAULT_MIN_AREA_PX,
) -> float:
    """Frame-level blob quality in ``[0, 1]`` (area + heading confidence)."""
    area_score = min(1.0, area / max(min_area_px, 1.0)) if area >= min_area_px else 0.0
    if heading_from_motion:
        motion_score = min(1.0, speed / max(speed_epsilon_px, 1e-6))
    elif has_anatomical_hint:
        motion_score = 0.35
    else:
        motion_score = 0.0
    return float(0.25 * area_score + 0.75 * motion_score)
