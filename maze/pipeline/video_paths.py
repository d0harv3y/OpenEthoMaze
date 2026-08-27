"""
Resolve and store trial ``video_path`` values across machines.

Stored H5 attrs may reference lab drive letters (e.g. ``E:\\videos\\...``) while
local copies live under a different root. Configure prefix remaps in
``paths_local.py`` (see ``paths_local.example.py``) or pass runtime overrides from CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

_RUNTIME_REMAPS: list[tuple[str, str]] | None = None


def set_runtime_video_path_prefix_remaps(
    remaps: Sequence[tuple[str, str]] | None,
) -> None:
    """Override :data:`maze.pipeline.paths.VIDEO_PATH_PREFIX_REMAPS` for one process."""
    global _RUNTIME_REMAPS
    if remaps is None:
        _RUNTIME_REMAPS = None
        return
    _RUNTIME_REMAPS = [(str(s), str(t)) for s, t in remaps]


def get_video_path_prefix_remaps() -> list[tuple[str, str]]:
    if _RUNTIME_REMAPS is not None:
        return list(_RUNTIME_REMAPS)
    from maze.pipeline.paths import VIDEO_PATH_PREFIX_REMAPS

    return list(VIDEO_PATH_PREFIX_REMAPS)


def remap_video_path(path: Path | str, remaps: Sequence[tuple[str, str]] | None = None) -> Path:
    """Apply configured prefix substitutions without checking file existence."""
    p = Path(path)
    parts = p.parts
    rules = list(remaps) if remaps is not None else get_video_path_prefix_remaps()
    for source, target in rules:
        src_parts = Path(source).parts
        if len(parts) < len(src_parts):
            continue
        if tuple(x.casefold() for x in parts[: len(src_parts)]) != tuple(
            x.casefold() for x in src_parts
        ):
            continue
        return Path(target, *parts[len(src_parts) :])
    return p


def resolve_input_h5_path(path: Path | str | None) -> Path | None:
    """Resolve a stored ``input_h5_path`` attr on this machine (same prefix remaps as video)."""
    return resolve_video_path(path)


def resolve_video_path(path: Path | str | None) -> Path | None:
    """
    Return a path that exists on this machine, applying prefix remaps when needed.

    Falls back to the original path when no remap yields an existing file.
    """
    if path is None:
        return None
    text = str(path).strip()
    if not text:
        return None

    original = Path(text)
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add(candidate: Path) -> None:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            candidates.append(candidate)

    _add(original)
    remapped = remap_video_path(original)
    _add(remapped)

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return remapped if remapped != original else original


def video_path_for_storage(path: Path | str | None) -> str | None:
    """Persist a ``video_path`` attr that resolves on this machine."""
    if path is None:
        return None
    text = str(path).strip()
    if not text:
        return None
    resolved = resolve_video_path(path)
    if resolved is not None and resolved.is_file():
        return str(resolved)
    return text
