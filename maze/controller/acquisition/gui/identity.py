from __future__ import annotations

import re
from typing import Optional

# Session ID is used in file paths and H5 keys; restrict to filename-safe characters.
# Underscore is excluded because it is the delimiter in video names (animal_session_trial).
SESSION_ID_ALLOWED_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
)


def sanitize_session_id(value: str) -> str:
    """Return value with only filename-safe characters."""
    return "".join(c for c in value if c in SESSION_ID_ALLOWED_CHARS)


def parse_virtual_video_identity(stem: str) -> Optional[tuple[str, str, str]]:
    """Parse virtual video stem into (animal_id, session_id, trial)."""
    parts = stem.split("_")
    if len(parts) >= 3:
        return (parts[0], parts[1], "_".join(parts[2:]))
    if len(parts) == 2:
        match = re.match(r"^(h?S\d+)(T\d+)$", parts[1], flags=re.IGNORECASE)
        if match:
            session_id, trial = match.group(1), match.group(2)
            return (parts[0], session_id, trial)
    return None
