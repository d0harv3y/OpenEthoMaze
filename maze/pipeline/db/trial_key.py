from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..io.file_discovery import TrialManifest


@dataclass(frozen=True)
class TrialKey:
    """Unique identifier for a trial in the database."""

    animal_id: str
    session: str
    trial: str

    def path(self) -> str:
        return f"/{self.animal_id}/{self.session}/{self.trial}"

    @property
    def phase(self) -> str:
        return "habituation" if self.session.upper().startswith("H") else "experimental"

    @classmethod
    def from_manifest(cls, manifest: "TrialManifest") -> "TrialKey":
        return cls(
            animal_id=manifest.animal_id,
            session=manifest.session,
            trial=manifest.trial,
        )
