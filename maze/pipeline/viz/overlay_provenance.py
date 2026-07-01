"""Record which files/feeds drive each unified-overlay layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

PoseKind = Literal["h5_anatomical", "sleap_sidecar", "none"]


@dataclass(frozen=True)
class OverlayPoseProvenance:
    """Where skeleton / pose-centroid data came from."""

    kind: PoseKind
    h5_path: str | None = None
    sleap_path: str | None = None
    pose_source_attr: str | None = None

    def summary(self) -> str:
        if self.kind == "h5_anatomical" and self.h5_path:
            extra = f", pose_source={self.pose_source_attr}" if self.pose_source_attr else ""
            return f"tracking/anatomical @ {self.h5_path}{extra}"
        if self.kind == "sleap_sidecar" and self.sleap_path:
            return f"sleap sidecar @ {self.sleap_path}"
        return "none"


@dataclass(frozen=True)
class OverlayDataProvenance:
    """Per-layer data sources for one rendered overlay clip."""

    video: str
    pipeline_h5: str
    tracking_h5: str | None
    ambulation_point: str
    trajectory_dot: str
    trajectory_dot_detail: str
    skeleton: str
    skeleton_detail: str
    ethogram_h5: str | None
    kpms_alignment: str | None
    arena_geometry: str
    hud_trial_state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def hud_lines(self) -> list[str]:
        """Short HUD lines (sources only)."""
        lines = [
            "--- sources ---",
            f"video: {self.video}",
            f"dot: {self.trajectory_dot}",
            f"skel: {self.skeleton}",
        ]
        if self.ethogram_h5:
            lines.append(f"ethogram: {self.ethogram_h5}")
        if self.kpms_alignment:
            lines.append(f"align: {self.kpms_alignment}")
        lines.append(f"arena: {self.arena_geometry}")
        lines.append(f"hud state: {self.hud_trial_state}")
        return lines
