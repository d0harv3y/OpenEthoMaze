"""Oriented blob polygon overlay and exit overlap helpers."""

from __future__ import annotations

import numpy as np
import pytest

from maze.controller.acquisition.gui.overlay_helpers import (
    blob_exit_overlap_fraction,
    draw_blob_polygon_on_overlay,
)

cv2 = pytest.importorskip("cv2")


def test_blob_exit_overlap_fraction_uses_vertices() -> None:
    # Square around (50, 50); exit at center with radius 10
    blob_xy = np.array(
        [
            [45.0, 45.0],
            [55.0, 45.0],
            [55.0, 55.0],
            [45.0, 55.0],
            [45.0, 45.0],
            [45.0, 45.0],
            [45.0, 45.0],
            [45.0, 45.0],
        ],
        dtype=np.float32,
    )
    frac = blob_exit_overlap_fraction(blob_xy, 50.0, 50.0, 12.0)
    assert frac == 1.0

    far_xy = blob_xy + np.array([100.0, 0.0], dtype=np.float32)
    assert blob_exit_overlap_fraction(far_xy, 50.0, 50.0, 12.0) == 0.0


def test_draw_blob_polygon_on_overlay() -> None:
    overlay = np.zeros((80, 80, 3), dtype=np.uint8)
    blob_xy = np.array(
        [
            [20.0, 20.0],
            [40.0, 20.0],
            [40.0, 40.0],
            [20.0, 40.0],
            [20.0, 20.0],
            [20.0, 20.0],
            [20.0, 20.0],
            [20.0, 20.0],
        ],
        dtype=np.float32,
    )
    draw_blob_polygon_on_overlay(overlay, blob_xy)
    assert int(overlay[30, 30, 1]) > 0
