from __future__ import annotations

ARENA_TYPE_CIRCULAR = "circular"
ARENA_TYPE_RADIAL_ARM = "radial_arm"

SUPPORTED_ARENA_TYPES: frozenset[str] = frozenset(
    {ARENA_TYPE_CIRCULAR, ARENA_TYPE_RADIAL_ARM}
)


def normalize_arena_type(value: object) -> str:
    """Normalize persisted arena/task labels to known values."""
    normalized = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized in SUPPORTED_ARENA_TYPES:
        return normalized
    return ARENA_TYPE_CIRCULAR
