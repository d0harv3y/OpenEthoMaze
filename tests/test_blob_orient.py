"""Motion-oriented blob contour resampling (Phase T1c)."""

from __future__ import annotations

import numpy as np
import pytest

from maze.core.anatomy import BLOB_VERTEX_COUNT, STANDARD_NODE_NAMES
from maze.pipeline.blob_orient import (
    BlobOrientTracker,
    anatomical_heading_hint,
    orient_vertices_by_heading,
    resample_contour,
    temporal_unwrap,
)


def _ellipse_contour(
    cx: float,
    cy: float,
    a: float,
    b: float,
    *,
    n: int = 128,
    rotation_rad: float = 0.0,
) -> np.ndarray:
    t = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    cos_r = np.cos(rotation_rad)
    sin_r = np.sin(rotation_rad)
    x = cx + a * np.cos(t) * cos_r - b * np.sin(t) * sin_r
    y = cy + a * np.cos(t) * sin_r + b * np.sin(t) * cos_r
    return np.column_stack([x, y])


def test_resample_contour_even_spacing_on_ellipse() -> None:
    contour = _ellipse_contour(50.0, 50.0, 30.0, 15.0)
    pts = resample_contour(contour, BLOB_VERTEX_COUNT)
    assert pts.shape == (BLOB_VERTEX_COUNT, 2)
    seg = np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)
    assert seg.std() / seg.mean() == pytest.approx(0.0, abs=0.15)


def test_orient_vertices_places_front_on_heading() -> None:
    contour = _ellipse_contour(0.0, 0.0, 40.0, 20.0)
    resampled = resample_contour(contour, BLOB_VERTEX_COUNT)
    centroid = resampled.mean(axis=0)
    oriented = orient_vertices_by_heading(resampled, centroid, heading_rad=0.0)
    front = oriented[0]
    angle = np.arctan2(front[1] - centroid[1], front[0] - centroid[0])
    assert angle == pytest.approx(0.0, abs=0.35)


def test_tracker_stable_order_under_eastward_motion() -> None:
    tracker = BlobOrientTracker(speed_epsilon_px=0.5, min_area_px=10.0)
    orders: list[np.ndarray] = []
    centroids: list[np.ndarray] = []

    for i in range(8):
        cx = 100.0 + i * 5.0
        frame = tracker.process_contour(_ellipse_contour(cx, 200.0, 35.0, 18.0))
        assert frame.valid
        if i > 0:
            assert frame.heading_rad == pytest.approx(0.0, abs=0.2)
            assert frame.score > 0.5
            front_angle = np.arctan2(
                frame.xy[0, 1] - frame.centroid[1],
                frame.xy[0, 0] - frame.centroid[0],
            )
            assert front_angle == pytest.approx(0.0, abs=0.35)
        orders.append(frame.xy.copy())
        centroids.append(frame.centroid.copy())

    for idx in range(1, len(orders)):
        prev, cur = orders[idx - 1], orders[idx]
        shift = centroids[idx] - centroids[idx - 1]
        aligned = cur - shift
        dists = [float(np.linalg.norm(np.roll(aligned, -k, axis=0) - prev)) for k in range(BLOB_VERTEX_COUNT)]
        assert min(dists) == pytest.approx(0.0, abs=2.5)


def test_low_speed_yields_nan_heading_and_low_score() -> None:
    tracker = BlobOrientTracker(speed_epsilon_px=5.0, min_area_px=10.0)
    tracker.process_contour(_ellipse_contour(100.0, 100.0, 30.0, 20.0))
    still = tracker.process_contour(_ellipse_contour(101.0, 100.0, 30.0, 20.0))
    assert still.valid
    assert np.isnan(still.heading_rad)
    assert still.score < 0.5


def test_anatomical_hint_orients_when_speed_low() -> None:
    tracker = BlobOrientTracker(speed_epsilon_px=5.0, min_area_px=10.0)
    tracker.process_contour(_ellipse_contour(100.0, 100.0, 30.0, 20.0))

    names = list(STANDARD_NODE_NAMES)
    pose = np.full((len(names), 2), np.nan)
    pose[names.index("neck")] = [90.0, 100.0]
    pose[names.index("nose")] = [130.0, 100.0]

    frame = tracker.process_contour(
        _ellipse_contour(101.0, 100.0, 30.0, 20.0),
        anatomical_pose_xy=pose,
        anatomical_node_names=names,
    )
    assert frame.valid
    assert np.isnan(frame.heading_rad)
    assert frame.score > 0.0
    front_angle = np.arctan2(frame.xy[0, 1] - 100.0, frame.xy[0, 0] - 100.0)
    assert front_angle == pytest.approx(0.0, abs=0.5)


def test_anatomical_heading_hint_neck_to_nose() -> None:
    names = list(STANDARD_NODE_NAMES)
    pose = np.zeros((len(names), 2))
    pose[names.index("neck")] = [0.0, 0.0]
    pose[names.index("nose")] = [10.0, 0.0]
    assert anatomical_heading_hint(pose, names) == pytest.approx(0.0)


def test_temporal_unwrap_prefers_continuity() -> None:
    prev = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float64)
    cur = np.roll(prev, 2, axis=0)
    unwrapped = temporal_unwrap(cur, prev)
    np.testing.assert_allclose(unwrapped, prev)


def test_process_mask_from_synthetic_ellipse() -> None:
    tracker = BlobOrientTracker(speed_epsilon_px=0.5, min_area_px=10.0)
    mask = np.zeros((120, 120), dtype=np.uint8)
    contour = _ellipse_contour(60.0, 60.0, 25.0, 12.0, n=64)
    xs = np.clip(np.round(contour[:, 0]).astype(int), 0, mask.shape[1] - 1)
    ys = np.clip(np.round(contour[:, 1]).astype(int), 0, mask.shape[0] - 1)
    mask[ys, xs] = 255

    frame = tracker.process_mask(mask)
    assert frame.valid
    assert frame.xy.shape == (BLOB_VERTEX_COUNT, 2)
    assert np.isfinite(frame.xy).all()
