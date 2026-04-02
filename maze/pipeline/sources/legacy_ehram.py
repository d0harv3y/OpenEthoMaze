"""Legacy `ehram` source adapter with lightweight discovery ported into ORM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ...core.tasks import ARENA_TYPE_RADIAL_ARM
from ..work_items import SourceWorkItem


@dataclass(frozen=True)
class VideoPair:
    video_path: Path
    sleap_path: Path


def iter_video_sleap_pairs(base_dir: Path | str) -> Iterator[VideoPair]:
    """
    Walk ``base_dir`` recursively and yield ``(.mp4, .h5.slp)`` pairs with the same stem.
    """
    base = Path(base_dir)
    if not base.exists():
        return

    for mp4_path in base.rglob("*.mp4"):
        sleap_path = mp4_path.with_suffix(".h5.slp")
        if sleap_path.exists():
            yield VideoPair(video_path=mp4_path, sleap_path=sleap_path)


def parse_minimal_metadata_from_filename(filename: str) -> dict[str, str]:
    """Infer a few coarse identity fields from a legacy `ehram` filename."""
    name = Path(filename).stem
    lowered = name.lower()

    animal_match = re.match(r"^\s*(\d+)", name)
    animal_id = animal_match.group(1) if animal_match else ""

    phase = ""
    if "training" in lowered:
        phase = "training"
    elif "recovery" in lowered:
        phase = "recovery"
    elif "sd day" in lowered or "sd" in lowered:
        phase = "sd"
    elif "hab" in lowered:
        phase = "habituation"

    trial_token = ""
    trial_match = re.search(r"\btrial[\s_#-]*([A-Za-z0-9]+)", name, flags=re.IGNORECASE)
    if trial_match:
        trial_token = trial_match.group(1)

    date_token = ""
    date_match = re.search(r"\b(\d{2}-\d{2}-\d{2})\b", name)
    if date_match:
        date_token = date_match.group(1)

    return {
        "animal_id": animal_id,
        "phase": phase,
        "trial": trial_token,
        "date": date_token,
        "raw_name": name,
    }


def _normalize_token(value: str, prefix: str, fallback: str) -> str:
    """Build a stable token for session/trial identifiers without claiming semantics."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    if not cleaned:
        cleaned = fallback
    return f"{prefix}{cleaned[:24]}"


def video_pair_to_work_item(pair: VideoPair) -> SourceWorkItem:
    """Normalize a paired legacy `ehram` recording into the shared source contract."""
    meta = parse_minimal_metadata_from_filename(pair.video_path.name)
    animal_id = meta["animal_id"] or "unknown"
    phase = meta["phase"] or "legacy"
    session_key = _normalize_token(meta["date"] or phase, "L", "legacy_session")
    trial_key = _normalize_token(meta["trial"] or meta["raw_name"], "T", "trial")

    return SourceWorkItem(
        source_name="legacy_ehram",
        arena_type=ARENA_TYPE_RADIAL_ARM,
        animal_id=animal_id,
        session_key=session_key,
        trial_key=trial_key,
        phase=phase,
        input_h5_path=None,
        video_path=pair.video_path,
        sleap_path=pair.sleap_path,
        raw_name=meta["raw_name"],
        metadata={
            "date": meta["date"],
            "phase": phase,
            "trial_token": meta["trial"],
            "source_dir": pair.video_path.parent.name,
        },
    )


def discover_legacy_ehram_work_items(base_dir: Path | str) -> list[SourceWorkItem]:
    """Discover paired legacy `ehram` recordings without importing the old package."""
    return [video_pair_to_work_item(pair) for pair in iter_video_sleap_pairs(base_dir)]


__all__ = [
    "VideoPair",
    "discover_legacy_ehram_work_items",
    "iter_video_sleap_pairs",
    "parse_minimal_metadata_from_filename",
    "video_pair_to_work_item",
]
