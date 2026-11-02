"""Filename stem recovery for orphan stop packs (no FastAPI import)."""

from __future__ import annotations

import re
from typing import Any


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s.strip()).strip("-") or "unknown"


def parse_part_stem(stem: str, cam_id: str) -> dict[str, Any] | None:
    """Mirror of app.main.parse_part_stem for unit test without FastAPI."""
    cam = _slug(cam_id)
    name = stem[:-3] if stem.endswith(".ts") else str(stem)
    marker = f"__{cam}__p"
    idx = name.rfind(marker)
    if idx < 0:
        return None
    head = name[:idx]
    try:
        part = int(name[idx + len(marker) :])
    except ValueError:
        return None
    bits = head.split("__")
    if len(bits) >= 2:
        subject_id, recording_tag = bits[0], bits[1]
    elif len(bits) == 1 and bits[0]:
        subject_id, recording_tag = bits[0], "ses"
    else:
        return None
    if not subject_id or subject_id == "unknown":
        return None
    return {
        "subject_id": subject_id,
        "recording_tag": recording_tag,
        "part": part,
        "stem": name,
    }


def test_parse_tagged_stem() -> None:
    p = parse_part_stem("test__ses__bhvr-cam0__p000", "bhvr-cam0")
    assert p is not None
    assert p["subject_id"] == "test"
    assert p["recording_tag"] == "ses"
    assert p["part"] == 0


def test_parse_rejects_unknown_subject() -> None:
    assert parse_part_stem("unknown__ses__bhvr-cam0__p000", "bhvr-cam0") is None


def test_parse_wrong_cam() -> None:
    assert parse_part_stem("test__ses__bhvr-cam1__p000", "bhvr-cam0") is None
