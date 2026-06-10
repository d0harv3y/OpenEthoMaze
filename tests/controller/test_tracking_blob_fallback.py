"""Backup blob contour fallback when inference uses a crop but SLEAP uses the full frame."""

from __future__ import annotations

import numpy as np
import pytest

from maze.controller.acquisition.tracking import (
    AdaptiveThresholdTracker,
    TrackingResult,
    full_frame_fallback_blob_contour,
)

cv2 = pytest.importorskip("cv2")


def _dark_disk(shape: tuple[int, int], cx: int, cy: int, radius: int) -> np.ndarray:
    img = np.full(shape, 220, dtype=np.uint8)
    cv2.circle(img, (cx, cy), radius, 40, -1)
    return img


def test_full_frame_fallback_blob_contour_retries_on_full_image() -> None:
    fallback = AdaptiveThresholdTracker(min_area=20, range_low=0, range_high=128)
    crop = np.full((40, 40), 220, dtype=np.uint8)
    full = _dark_disk((100, 100), 50, 50, 18)

    crop_res = fallback.track(crop)
    assert crop_res.blob_contour is None

    contour = full_frame_fallback_blob_contour(fallback, crop, crop_res, full)
    assert contour is not None
    assert contour.ndim == 2 and contour.shape[1] == 2
    assert contour.shape[0] >= 3


def test_full_frame_fallback_returns_crop_contour_when_present() -> None:
    fallback = AdaptiveThresholdTracker(min_area=20, range_low=0, range_high=128)
    crop = _dark_disk((60, 60), 30, 30, 14)
    full = _dark_disk((100, 100), 50, 50, 18)

    crop_res = fallback.track(crop)
    assert crop_res.blob_contour is not None

    contour = full_frame_fallback_blob_contour(fallback, crop, crop_res, full)
    assert contour is crop_res.blob_contour


def test_full_frame_fallback_skips_when_same_shape() -> None:
    fallback = AdaptiveThresholdTracker(min_area=20, range_low=0, range_high=128)
    img = np.full((50, 50), 220, dtype=np.uint8)
    crop_res = TrackingResult(0.0, 0.0, False, "fallback")

    assert full_frame_fallback_blob_contour(fallback, img, crop_res, img.copy()) is None
