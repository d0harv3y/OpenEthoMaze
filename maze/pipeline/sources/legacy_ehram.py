"""Legacy `ehram` source adapter using ORM-owned sidecar contracts."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from ...core.tasks import ARENA_TYPE_RADIAL_ARM
from ..work_items import SourceWorkItem


@dataclass(frozen=True)
class VideoPair:
    video_path: Path
    sleap_path: Path


@dataclass(frozen=True)
class LegacyRamSidecarRow:
    """Authoritative legacy RAM trial metadata from ``trial_ns.csv``."""

    parent_directory: str
    file_name: str
    animal_id: str
    tx: str
    sex: str
    phase: str
    trial: str
    escape_arm: int
    start_datetime: datetime | None

    @property
    def session_key(self) -> str:
        return normalize_legacy_ram_session(self.phase)

    @property
    def trial_key(self) -> str:
        trial_value = str(self.trial).strip()
        if trial_value.isdigit():
            return f"T{int(trial_value):02d}"
        return trial_value or "T00"


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


def normalize_legacy_ram_session(phase: str) -> str:
    """Normalize legacy phase labels into filename-safe session keys."""
    value = str(phase or "").strip().replace("_", "-")
    return value or "legacy-ram"


def _parse_start_datetime(raw_value: str) -> datetime | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def load_trial_ns_rows(csv_path: Path | str) -> list[LegacyRamSidecarRow]:
    """Load authoritative legacy RAM sidecar rows from ``trial_ns.csv``."""
    path = Path(csv_path)
    if not path.exists():
        return []

    rows: list[LegacyRamSidecarRow] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                LegacyRamSidecarRow(
                    parent_directory=str(row.get("parent_directory", "")).strip(),
                    file_name=str(row.get("file_name", "")).strip(),
                    animal_id=str(row.get("id", "")).strip(),
                    tx=str(row.get("tx", "")).strip(),
                    sex=str(row.get("sex", "")).strip(),
                    phase=str(row.get("phase", "")).strip(),
                    trial=str(row.get("trial", "")).strip(),
                    escape_arm=int(str(row.get("escape_arm", "0") or "0").strip()),
                    start_datetime=_parse_start_datetime(row.get("start_datetime", "")),
                )
            )
    return rows


def build_trial_ns_index(
    rows: list[LegacyRamSidecarRow],
) -> dict[tuple[str, str], LegacyRamSidecarRow]:
    """Index sidecar rows by ``(parent_directory, file_name)``."""
    index: dict[tuple[str, str], LegacyRamSidecarRow] = {}
    for row in rows:
        key = (row.parent_directory.casefold(), row.file_name.casefold())
        index[key] = row
    return index


def find_trial_ns_row(
    video_path: Path | str,
    csv_path: Path | str,
) -> Optional[LegacyRamSidecarRow]:
    """Look up one video in the authoritative ``trial_ns.csv`` mapping."""
    path = Path(video_path)
    key = (path.parent.name.casefold(), path.name.casefold())
    return build_trial_ns_index(load_trial_ns_rows(csv_path)).get(key)


def sidecar_row_to_work_item(
    row: LegacyRamSidecarRow,
    *,
    video_path: Path,
    sleap_path: Path,
) -> SourceWorkItem:
    """Normalize one authoritative legacy RAM row into the shared work-item contract."""

    return SourceWorkItem(
        source_name="legacy_ehram",
        arena_type=ARENA_TYPE_RADIAL_ARM,
        animal_id=row.animal_id or "unknown",
        session_key=row.session_key,
        trial_key=row.trial_key,
        phase=row.phase or "legacy",
        input_h5_path=None,
        video_path=video_path,
        sleap_path=sleap_path,
        timestamp=row.start_datetime,
        raw_name=Path(row.file_name).stem,
        metadata={
            "parent_directory": row.parent_directory,
            "file_name": row.file_name,
            "phase": row.phase,
            "trial": row.trial,
            "escape_arm": str(row.escape_arm),
            "tx": row.tx,
            "sex": row.sex,
            "start_datetime": (
                row.start_datetime.isoformat() if row.start_datetime is not None else ""
            ),
        },
    )


def discover_legacy_ehram_work_items(
    base_dir: Path | str,
    *,
    trial_ns_path: Path | str | None = None,
) -> list[SourceWorkItem]:
    """Discover paired legacy RAM recordings using authoritative sidecars."""
    if trial_ns_path is None:
        return []

    rows = load_trial_ns_rows(trial_ns_path)
    row_index = build_trial_ns_index(rows)
    work_items: list[SourceWorkItem] = []
    for pair in iter_video_sleap_pairs(base_dir):
        key = (pair.video_path.parent.name.casefold(), pair.video_path.name.casefold())
        row = row_index.get(key)
        if row is None:
            continue
        work_items.append(
            sidecar_row_to_work_item(
                row,
                video_path=pair.video_path,
                sleap_path=pair.sleap_path,
            )
        )
    return work_items


__all__ = [
    "LegacyRamSidecarRow",
    "VideoPair",
    "build_trial_ns_index",
    "discover_legacy_ehram_work_items",
    "find_trial_ns_row",
    "iter_video_sleap_pairs",
    "load_trial_ns_rows",
    "normalize_legacy_ram_session",
    "sidecar_row_to_work_item",
]
