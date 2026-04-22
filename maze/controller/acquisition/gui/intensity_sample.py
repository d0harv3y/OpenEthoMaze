"""Grayscale sampling for backup tracking (same luminance as ``tracking._ensure_grayscale``)."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore[misc, assignment]


def gray_value_at_pixel_bgr(img_bgr_u8: np.ndarray, ix: int, iy: int) -> Optional[int]:
    """Return 0–255 gray at integer pixel (``ix``, ``iy``), or None if out of bounds."""
    if img_bgr_u8.ndim == 2:
        h, w = img_bgr_u8.shape[:2]
        if 0 <= iy < h and 0 <= ix < w:
            return int(img_bgr_u8[iy, ix])
        return None
    if img_bgr_u8.ndim != 3 or img_bgr_u8.shape[2] < 3:
        return None
    h, w = img_bgr_u8.shape[:2]
    if not (0 <= iy < h and 0 <= ix < w):
        return None
    if cv2 is not None:
        g = cv2.cvtColor(
            img_bgr_u8[iy : iy + 1, ix : ix + 1],
            cv2.COLOR_BGR2GRAY,
        )
        return int(g[0, 0])
    b, g, r = (int(img_bgr_u8[iy, ix, 0]), int(img_bgr_u8[iy, ix, 1]), int(img_bgr_u8[iy, ix, 2]))
    return int(round(0.114 * b + 0.587 * g + 0.299 * r))


def gray_neighborhood_patch_bgr(
    img_bgr_u8: np.ndarray,
    ix: int,
    iy: int,
    half: int,
) -> Optional[np.ndarray]:
    """
    Extract a square neighborhood (``2*half+1``) around (``ix``, ``iy``), clipped to the image.

    Returns a 2D uint8 grayscale patch (same convention as tracking), or None if empty.
    """
    if half < 0:
        return None
    if img_bgr_u8.ndim == 2:
        h, w = img_bgr_u8.shape[:2]
        y0, y1 = max(0, iy - half), min(h, iy + half + 1)
        x0, x1 = max(0, ix - half), min(w, ix + half + 1)
        if y1 <= y0 or x1 <= x0:
            return None
        return np.asarray(img_bgr_u8[y0:y1, x0:x1], dtype=np.uint8)
    if img_bgr_u8.ndim != 3 or img_bgr_u8.shape[2] < 3:
        return None
    h, w = img_bgr_u8.shape[:2]
    y0, y1 = max(0, iy - half), min(h, iy + half + 1)
    x0, x1 = max(0, ix - half), min(w, ix + half + 1)
    if y1 <= y0 or x1 <= x0:
        return None
    crop = np.asarray(img_bgr_u8[y0:y1, x0:x1], dtype=np.uint8)
    if cv2 is not None:
        return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    b = crop[:, :, 0].astype(np.float64)
    gch = crop[:, :, 1].astype(np.float64)
    r = crop[:, :, 2].astype(np.float64)
    y = 0.114 * b + 0.587 * gch + 0.299 * r
    return np.clip(np.round(y), 0, 255).astype(np.uint8)


def fallback_range_from_gray_patch(
    gray_patch: np.ndarray,
    delta: int,
) -> Tuple[int, int]:
    """
    From min/max gray in ``gray_patch``, return ``(range_low, range_high)`` with ±delta, clamped to 0–255.

    If ``gray_patch`` is empty, returns ``(0, 255)``.
    """
    if gray_patch.size == 0:
        return (0, 255)
    gmin = int(np.min(gray_patch))
    gmax = int(np.max(gray_patch))
    d = max(0, int(delta))
    lo = max(0, gmin - d)
    hi = min(255, gmax + d)
    if lo > hi:
        lo, hi = hi, lo
    return (lo, hi)
