from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class SourceWorkItem:
    """Normalized offline work item produced by any legacy source adapter."""

    source_name: str
    arena_type: str
    animal_id: str
    session_key: str
    trial_key: str
    phase: str | None = None
    input_h5_path: Path | None = None
    video_path: Path | None = None
    sleap_path: Path | None = None
    timestamp: datetime | None = None
    cohort: str | None = None
    researcher: str | None = None
    raw_name: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def work_key(self) -> str:
        return (
            f"{self.source_name}:{self.arena_type}:"
            f"{self.animal_id}/{self.session_key}/{self.trial_key}"
        )
