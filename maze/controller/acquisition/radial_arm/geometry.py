from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

Point = tuple[float, float]
RegionPolygons = Mapping[str, np.ndarray]


@dataclass(frozen=True)
class RadialArmTemplateGeometry:
    """Canonical RAM template geometry expressed in centimeter coordinates."""

    regions_cm: RegionPolygons
    arm_angles_rad: tuple[float, ...]
    apothem_cm: float
    arm_length_cm: float
    arm_width_cm: float
    arm_split_cm: float
    hole_arm_index: int
    hole_radius_cm: float
    hole_inset_from_arm_end_cm: float


def _regular_ngon_vertices(
    n: int,
    apothem: float,
    rotation_rad: float = 0.0,
) -> np.ndarray:
    """Build vertices for a regular n-gon centered at the origin."""
    circumradius = float(apothem) / float(np.cos(np.pi / n))
    angles = rotation_rad + (2.0 * np.pi * np.arange(n) / n)
    x = circumradius * np.cos(angles)
    y = circumradius * np.sin(angles)
    return np.stack([x, y], axis=1)


def _rect_along_axis(
    base_center: Point,
    axis_angle: float,
    length: float,
    width: float,
) -> np.ndarray:
    """Return a rectangle whose long axis points at ``axis_angle``."""
    bx, by = base_center
    cos_a = float(np.cos(axis_angle))
    sin_a = float(np.sin(axis_angle))
    ux, uy = cos_a, sin_a
    vx, vy = -sin_a, cos_a

    half_width = float(width) / 2.0
    p0 = (bx + vx * half_width, by + vy * half_width)
    p1 = (bx - vx * half_width, by - vy * half_width)
    far_x = bx + ux * float(length)
    far_y = by + uy * float(length)
    p2 = (far_x - vx * half_width, far_y - vy * half_width)
    p3 = (far_x + vx * half_width, far_y + vy * half_width)
    return np.array([p0, p1, p2, p3], dtype=float)


def build_template_from_params(
    *,
    center_midedge_to_midedge_cm: float = 80.0,
    arm_length_cm: float = 55.0,
    arm_width_cm: float = 15.0,
    arm_split_cm: float | None = None,
    hole_arm_index: int = 0,
    hole_radius_cm: float = 5.0,
    hole_inset_from_arm_end_cm: float = 10.0,
) -> RadialArmTemplateGeometry:
    """Build the canonical RAM template from ORM-native parameters."""
    split_cm = (
        float(arm_split_cm)
        if arm_split_cm is not None
        else float(arm_length_cm) / 2.0
    )
    apothem_cm = float(center_midedge_to_midedge_cm) / 2.0

    n_sides = 16
    rotation = float(np.pi / n_sides)
    center_poly = _regular_ngon_vertices(
        n=n_sides,
        apothem=apothem_cm,
        rotation_rad=rotation,
    )

    arm_angles = tuple(float(k * (np.pi / 4.0)) for k in range(8))
    regions: dict[str, np.ndarray] = {"center": center_poly}

    clamped_split = float(max(0.0, min(float(arm_length_cm), split_cm)))
    hole_arm_index = int(max(0, min(7, hole_arm_index)))

    for arm_index, angle in enumerate(arm_angles):
        base_mid = (
            apothem_cm * float(np.cos(angle)),
            apothem_cm * float(np.sin(angle)),
        )
        front_poly = _rect_along_axis(
            base_center=base_mid,
            axis_angle=angle,
            length=clamped_split,
            width=float(arm_width_cm),
        )

        ux, uy = float(np.cos(angle)), float(np.sin(angle))
        back_length = float(max(0.0, float(arm_length_cm) - clamped_split))
        back_base_mid = (
            base_mid[0] + ux * clamped_split,
            base_mid[1] + uy * clamped_split,
        )
        back_poly = _rect_along_axis(
            base_center=back_base_mid,
            axis_angle=angle,
            length=back_length,
            width=float(arm_width_cm),
        )

        regions[f"arm{arm_index}_front"] = front_poly
        regions[f"arm{arm_index}_back"] = back_poly

    hole_angle = arm_angles[hole_arm_index]
    ux, uy = float(np.cos(hole_angle)), float(np.sin(hole_angle))
    hole_base_mid = (
        apothem_cm * float(np.cos(hole_angle)),
        apothem_cm * float(np.sin(hole_angle)),
    )
    end_mid = (
        hole_base_mid[0] + ux * float(arm_length_cm),
        hole_base_mid[1] + uy * float(arm_length_cm),
    )
    hole_center = (
        end_mid[0] - ux * float(hole_inset_from_arm_end_cm),
        end_mid[1] - uy * float(hole_inset_from_arm_end_cm),
    )
    theta = np.linspace(0.0, 2.0 * np.pi, num=20, endpoint=False)
    hole_poly = np.stack(
        [
            hole_center[0] + float(hole_radius_cm) * np.cos(theta),
            hole_center[1] + float(hole_radius_cm) * np.sin(theta),
        ],
        axis=1,
    )
    regions["hole"] = hole_poly.astype(float)

    return RadialArmTemplateGeometry(
        regions_cm=regions,
        arm_angles_rad=arm_angles,
        apothem_cm=apothem_cm,
        arm_length_cm=float(arm_length_cm),
        arm_width_cm=float(arm_width_cm),
        arm_split_cm=clamped_split,
        hole_arm_index=hole_arm_index,
        hole_radius_cm=float(hole_radius_cm),
        hole_inset_from_arm_end_cm=float(hole_inset_from_arm_end_cm),
    )


def build_template() -> RadialArmTemplateGeometry:
    """Build the default canonical RAM template."""
    return build_template_from_params()
