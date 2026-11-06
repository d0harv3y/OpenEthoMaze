"""Litmus: 22-D skeleton dims, z-score leaves P raw, centered window width."""

from __future__ import annotations

import numpy as np
import pytest

from of_rear_classifier.arena import point_in_polygon
from of_rear_classifier.bout import avgbool, bout_count
from of_rear_classifier.labels import intervals_to_frame_labels
from of_rear_classifier.mlp import MlpSpec, build_torch_mlp
from of_rear_classifier.parts_map import SA_TVM_PARTS
from of_rear_classifier.skeleton import (
    FEATURE_NAMES,
    N_FEATURES,
    angle_between_segments,
    skeleton_features,
    zscore_skeleton,
)
from of_rear_classifier.window import stack_centered, window_feature_dim


def _toy_parts(t: int = 100, seed: int = 0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    # Rough mouse-like chain along +x
    base = np.cumsum(rng.normal(0, 0.5, size=(t, 2)), axis=0)
    parts = {}
    offsets = {
        "nose": (20.0, 0.0),
        "head_midpoint": (15.0, 0.0),
        "neck": (10.0, 0.0),
        "mouse_center": (0.0, 0.0),
        "left_midside": (0.0, 5.0),
        "right_midside": (0.0, -5.0),
        "left_hip": (-8.0, 4.0),
        "right_hip": (-8.0, -4.0),
        "left_ear": (16.0, 3.0),
        "right_ear": (16.0, -3.0),
        "tail_base": (-12.0, 0.0),
        "tail2": (-18.0, 0.0),
        "tail_end": (-24.0, 0.0),
    }
    for name in SA_TVM_PARTS:
        ox, oy = offsets[name]
        parts[name] = base + np.array([ox, oy]) + rng.normal(0, 0.1, size=(t, 2))
    return parts


def test_feature_names_count():
    assert len(FEATURE_NAMES) == 22
    assert N_FEATURES == 22


def test_skeleton_shape_and_positive_lengths():
    parts = _toy_parts(80)
    f = skeleton_features(parts)
    assert f.shape == (80, 22)
    assert np.all(f[:, :10] >= 0)  # lengths
    assert np.all(f[:, 10:16] >= 0)  # angles in [0, pi]
    assert np.all(f[:, 10:16] <= np.pi + 1e-6)
    assert np.all(f[:, 16:20] >= 0)  # areas


def test_colinear_angle_is_pi():
    t = 5
    p2 = np.zeros((t, 2))
    p1 = np.column_stack([np.ones(t), np.zeros(t)])  # p1-p2 = (1, 0)
    p3 = np.zeros((t, 2))
    p4 = np.column_stack([np.ones(t), np.zeros(t)])  # p3-p4 = (-1, 0)
    # vectors (1,0) and (-1,0) → angle π
    ang = angle_between_segments(p1, p2, p3, p4)
    assert ang.shape == (t,)
    np.testing.assert_allclose(ang, np.pi, rtol=0, atol=1e-5)


def test_zscore_leaves_p_flags():
    parts = _toy_parts(60)
    p1 = np.ones(60)
    p2 = np.zeros(60)
    f = skeleton_features(parts, in_arena_nose=p1, in_arena_head=p2)
    z = zscore_skeleton(f)
    np.testing.assert_array_equal(z[:, 20], p1)
    np.testing.assert_array_equal(z[:, 21], p2)
    # continuous cols roughly zero-mean
    assert abs(np.mean(z[:, 0])) < 1e-6


def test_centered_window_shape():
    t, w = 100, 15
    f = np.arange(t * N_FEATURES, dtype=np.float64).reshape(t, N_FEATURES)
    x, y = stack_centered(f, integration_window=w, labels=np.arange(t))
    assert x.shape == (t - 2 * w, window_feature_dim(w))
    assert x.shape[1] == 682
    assert y is not None
    assert y.shape == (t - 2 * w,)
    assert y[0] == w
    # center row 0 uses frames [0, 2w] flattened
    np.testing.assert_array_equal(x[0], f[0 : 2 * w + 1].ravel())


def test_point_in_square():
    verts = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])
    xy = np.array([[5.0, 5.0], [15.0, 5.0], [-1.0, 5.0]])
    inside = point_in_polygon(xy, verts)
    np.testing.assert_array_equal(inside, [1.0, 0.0, 0.0])


def test_labels_and_bouts():
    import pandas as pd

    intervals = pd.DataFrame(
        {
            "from": [1.0, 3.0],
            "to": [2.0, 4.0],
            "type": ["Supported", "Unsupported"],
        }
    )
    y = intervals_to_frame_labels(intervals, n_frames=100, fps=25.0)
    assert y[25] == "Supported"  # t=1.0s
    assert y[80] == "Unsupported"  # t=3.2s roughly in [3,4]
    mask = y == "Supported"
    smooth = avgbool(mask, window=2)
    assert bout_count(smooth) >= 1


def test_mlp_spec_optional_torch():
    spec = MlpSpec(n_in=682, n_classes=4)
    try:
        import torch  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match="torch"):
            build_torch_mlp(spec)
        return
    model = build_torch_mlp(spec)
    import torch

    x = torch.randn(8, 682)
    y = model(x)
    assert y.shape == (8, 4)
