"""Unified overlay job configuration (no cv2 import — safe for CI)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class UnifiedOverlayRunConfig:
    """Inputs for a single unified overlay render (CLI or GUI)."""

    manifest_csv: Path
    pipeline_h5: Path
    animal_id: str
    session: str
    trial: str
    out: Path
    kpms_h5: Optional[Path] = None
    kpms_training_exemplars: Optional[Path] = None
    no_hypnogram: bool = False
    no_syllable_tray: bool = False
    no_skeleton: bool = False
