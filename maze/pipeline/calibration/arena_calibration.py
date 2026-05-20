"""
Arena calibration module for VAST pipeline.

Handles parsing and validation of arena calibration parameters
from the input H5 settings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from ..defaults import DEFAULT_PX_PER_CM


@dataclass
class ArenaCalibration:
    """Container for arena calibration parameters from ROI string."""

    # Arena center position in pixels (from ROI X,Y)
    arena_center_x_px: float
    arena_center_y_px: float

    # Arena geometry
    arena_radius_px: float

    # Calibration factor
    px_per_cm: float

    @property
    def arena_center(self) -> tuple[float, float]:
        """Arena center position as tuple."""
        return (self.arena_center_x_px, self.arena_center_y_px)

    @property
    def arena_radius_cm(self) -> float:
        """Arena radius in cm."""
        return self.arena_radius_px / self.px_per_cm

    @property
    def cm_per_px(self) -> float:
        """Inverse calibration factor."""
        return 1.0 / self.px_per_cm if self.px_per_cm > 0 else 0.0


def parse_roi_string(roi_str: str) -> ArenaCalibration:
    """
    Parse ROI attribute string from H5 settings.

    The ROI string describes the arena perimeter and calibration:
    - X, Y: Arena center coordinates in pixels
    - R: Arena radius in pixels
    - pxcm: Calibration factor (pixels per cm)

    Args:
        roi_str: String like "X=187,Y=149,R=147,pxcm=2.422145"

    Returns:
        ArenaCalibration object
    """
    params = {}

    for match in re.finditer(r"(\w+)=([\d.]+)", roi_str):
        key = match.group(1).lower()
        value = float(match.group(2))
        params[key] = value

    return ArenaCalibration(
        arena_center_x_px=params.get("x", 0.0),
        arena_center_y_px=params.get("y", 0.0),
        arena_radius_px=params.get("r", 0.0),
        px_per_cm=params.get("pxcm", DEFAULT_PX_PER_CM),
    )


def validate_calibration(cal: ArenaCalibration) -> list[str]:
    """
    Validate calibration parameters.

    Returns list of warning messages (empty if valid).
    """
    warnings = []

    if cal.arena_radius_px <= 0:
        warnings.append("Arena radius is zero or negative")

    if cal.px_per_cm <= 0:
        warnings.append("Pixels per cm is zero or negative")

    if cal.arena_center_x_px <= 0 or cal.arena_center_y_px <= 0:
        warnings.append("Arena center has zero or negative coordinates")

    return warnings


def px_to_cm(
    xy_px: np.ndarray,
    origin: tuple[float, float],
    px_per_cm: float,
) -> np.ndarray:
    """
    Convert pixel coordinates to cm (relative to origin).

    Args:
        xy_px: Array of shape (n, 2) in pixels
        origin: Origin position in pixels (e.g., arena center or exit)
        px_per_cm: Calibration factor

    Returns:
        Array of shape (n, 2) in cm
    """
    xy_px = np.asarray(xy_px)
    origin_x, origin_y = origin

    xy_centered = xy_px - np.array([origin_x, origin_y])
    return xy_centered / px_per_cm


def cm_to_px(
    xy_cm: np.ndarray,
    origin: tuple[float, float],
    px_per_cm: float,
) -> np.ndarray:
    """
    Convert cm coordinates back to pixels.

    Args:
        xy_cm: Array of shape (n, 2) in cm (relative to origin)
        origin: Origin position in pixels
        px_per_cm: Calibration factor

    Returns:
        Array of shape (n, 2) in pixels
    """
    xy_cm = np.asarray(xy_cm)
    origin_x, origin_y = origin

    xy_px = xy_cm * px_per_cm
    return xy_px + np.array([origin_x, origin_y])
