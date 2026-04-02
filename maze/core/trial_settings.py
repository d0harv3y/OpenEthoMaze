"""Canonical trial-settings model shared across pipeline readers and storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TrialSettings:
    """Container for trial settings parsed from controller or legacy H5 data."""

    arena_center_x_px: float
    arena_center_y_px: float
    arena_radius_px: float
    px_per_cm: float
    stage: str
    color: str
    timestamp: Optional[datetime]
    exit_number: Optional[int] = None
    exit_x: Optional[float] = None
    exit_y: Optional[float] = None
    exit_radius_px: Optional[float] = None
    roi_old: Optional[str] = None

    @property
    def exit_pos(self) -> Optional[tuple[float, float]]:
        if self.exit_x is not None and self.exit_y is not None:
            return (self.exit_x, self.exit_y)
        return None

    @property
    def arena_radius_cm(self) -> float:
        return self.arena_radius_px / self.px_per_cm

    @property
    def exit_radius_cm(self) -> Optional[float]:
        if self.exit_radius_px is None or self.px_per_cm <= 0:
            return None
        return self.exit_radius_px / self.px_per_cm

    @property
    def cm_per_px(self) -> float:
        return 1.0 / self.px_per_cm if self.px_per_cm > 0 else 0.0


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse the timestamp strings seen in imported and controller-written H5 files."""
    formats = [
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str.strip(), fmt)
        except ValueError:
            continue

    return None
