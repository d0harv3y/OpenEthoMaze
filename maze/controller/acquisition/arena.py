"""
Arena geometry: center/edge zones, exit placement, distance to exit.

All positions in pixel coordinates unless noted; conversion to cm uses config.px_per_cm.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from .config import ArenaConfig, ExitAngleConfig


def distance_px(
    x1: float, y1: float,
    x2: float, y2: float
) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def in_center_region(
    x_px: float, y_px: float,
    config: ArenaConfig
) -> bool:
    """True if (x_px, y_px) is inside the center circle."""
    cx, cy = config.arena_center_x_px, config.arena_center_y_px
    d = distance_px(x_px, y_px, cx, cy)
    return d <= config.center_radius_px


def in_edge_region(
    x_px: float, y_px: float,
    config: ArenaConfig
) -> bool:
    """True if (x_px, y_px) is in the edge annulus (outside center, inside arena)."""
    cx, cy = config.arena_center_x_px, config.arena_center_y_px
    d = distance_px(x_px, y_px, cx, cy)
    return config.center_radius_px < d <= config.radius_px


def in_exit_zone(
    x_px: float, y_px: float,
    exit_x_px: float, exit_y_px: float,
    config: ArenaConfig
) -> bool:
    """True if (x_px, y_px) is within exit_radius_cm of exit center."""
    exit_radius_px = config.exit_radius_cm * config.px_per_cm
    d = distance_px(x_px, y_px, exit_x_px, exit_y_px)
    return d <= exit_radius_px


def distance_to_exit_cm(
    x_px: float, y_px: float,
    exit_x_px: float, exit_y_px: float,
    px_per_cm: float
) -> float:
    d_px = distance_px(x_px, y_px, exit_x_px, exit_y_px)
    return d_px / px_per_cm


def angle_from_center_deg(cx: float, cy: float, x: float, y: float) -> float:
    """Angle in degrees from center to (x,y); 0 = right, 90 = down (image coords)."""
    dx, dy = x - cx, y - cy
    return math.degrees(math.atan2(dy, dx))


def exit_center_px(
    rodent_x_px: float, rodent_y_px: float,
    exit_angle_index: int,
    arena: ArenaConfig,
    exit_angles: ExitAngleConfig
) -> Tuple[float, float]:
    """
    Place exit in center region: opposite side from rodent, then snap to trial angle.

    Returns (exit_x_px, exit_y_px). Exit is placed on the circle at center_radius_px
    (inner boundary of edge) so it stays in center region.
    """
    cx = arena.arena_center_x_px
    cy = arena.arena_center_y_px
    rodent_angle = angle_from_center_deg(cx, cy, rodent_x_px, rodent_y_px)
    opposite_deg = rodent_angle + 180.0
    trial_offset_deg = exit_angles.angle_deg(exit_angle_index)
    exit_angle_deg = opposite_deg + trial_offset_deg
    r = arena.center_radius_px - (arena.exit_radius_cm * arena.px_per_cm)
    r = max(r, 10.0)
    rad = math.radians(exit_angle_deg)
    ex = cx + r * math.cos(rad)
    ey = cy + r * math.sin(rad)
    return (ex, ey)


def _session_id_hash(session_id: str, seed: Optional[int]) -> int:
    """Stable integer from session_id for Latin square (deterministic across runs)."""
    h = seed if seed is not None else 0
    for c in session_id.encode("utf-8"):
        h = (h * 31 + c) & 0xFFFFFFFF
    return h


def latin_square_exit_index(
    session_id: str, trial_idx: int,
    n_angles: int, seed: Optional[int]
) -> int:
    """Return exit angle index 0..n_angles-1 for this session/trial (Latin square style).

    When seed is an int: permutation is deterministic for that seed (reproducible across runs).
    When seed is None: permutation is derived from session_id only (same session_id always
    gets the same order; deterministic per session across runs).
    """
    import random
    # Option C: session-deterministic when seed is None (same session_id → same permutation)
    effective_seed = seed if seed is not None else _session_id_hash(session_id, None)
    rng = random.Random(effective_seed)
    base = list(range(n_angles))
    rng.shuffle(base)
    session_part = _session_id_hash(session_id, seed)
    global_idx = session_part * 1000 + trial_idx
    return base[global_idx % n_angles]
