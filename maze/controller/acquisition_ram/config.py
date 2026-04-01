from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...core.tasks import ARENA_TYPE_RADIAL_ARM


@dataclass
class RadialArmControllerConfig:
    """Minimal RAM acquisition config until the dedicated controller lands."""

    arena_type: str = ARENA_TYPE_RADIAL_ARM
    output_dir: Optional[str] = None
    h5_filename: str = "ram_trials.h5"
