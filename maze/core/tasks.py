from __future__ import annotations

"""Supported arena/task labels shared across controller and pipeline code.

Task identity lives here, while task-specific arena geometry should live under
``maze.controller.acquisition`` task modules or future task packages. This keeps arena
layout choices separate from shared anatomy constants in ``maze.core.anatomy``.
"""

ARENA_TYPE_CIRCULAR = "circular"
ARENA_TYPE_RADIAL_ARM = "radial_arm"

SUPPORTED_ARENA_TYPES: frozenset[str] = frozenset({ARENA_TYPE_CIRCULAR, ARENA_TYPE_RADIAL_ARM})


def normalize_arena_type(value: object) -> str:
    """Normalize persisted arena/task labels to known values."""
    normalized = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized in SUPPORTED_ARENA_TYPES:
        return normalized
    return ARENA_TYPE_CIRCULAR
