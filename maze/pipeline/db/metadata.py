from __future__ import annotations

from pathlib import Path
from typing import Optional

from maze.core.h5_layout import init_task_database
from maze.core.tasks import ARENA_TYPE_CIRCULAR, normalize_arena_type

from ..defaults import get_config_snapshot
from ..paths import OUTPUT_H5
from ._shared import ensure_group, open_db, write_json_attr


def init_database(db_path: Optional[Path] = None) -> None:
    """Initialize pipeline metadata on top of the shared task-database bootstrap."""
    resolved_path = db_path or OUTPUT_H5
    arena_type = ARENA_TYPE_CIRCULAR
    arena_description: Optional[str] = (
        "Circular open field with distance-proportional vibration feedback"
    )
    try:
        with open_db(resolved_path, "r") as h5:
            meta = h5.get("metadata")
            if meta is not None:
                arena = meta.get("arena_info")
                if arena is not None and "type" in arena.attrs:
                    arena_type = normalize_arena_type(arena.attrs.get("type"))
                    if "description" in arena.attrs:
                        arena_description = str(arena.attrs.get("description") or "")
                    elif arena_type != ARENA_TYPE_CIRCULAR:
                        arena_description = None
    except OSError:
        pass

    init_task_database(
        resolved_path,
        arena_type=arena_type,
        arena_description=arena_description,
    )
    with open_db(resolved_path, "a") as h5:
        meta = ensure_group(h5, "metadata")
        write_json_attr(meta, "config_snapshot", get_config_snapshot())
        ensure_group(meta, "animal_labels")


def read_arena_type(db_path: Optional[Path]) -> str:
    """Read the persisted arena/task type for the database."""
    try:
        with open_db(db_path, "r") as h5:
            meta = h5.get("metadata")
            if meta is None:
                return ARENA_TYPE_CIRCULAR
            arena = meta.get("arena_info")
            if arena is None:
                return ARENA_TYPE_CIRCULAR
            return normalize_arena_type(arena.attrs.get("type"))
    except OSError:
        return ARENA_TYPE_CIRCULAR
