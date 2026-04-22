from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AnimalInfo:
    """Per-animal metadata."""

    animal_id: str
    tx: Optional[str] = None
    strain: Optional[str] = None
    sex: Optional[str] = None
    drug: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class SessionConfig:
    """Shared session and roster settings for acquisition tasks."""

    num_animals: int = 1
    num_trials: int = 9
    max_trial_duration_s: float = 120.0
    iti_s: float = 10.0
    seed: Optional[int] = None
    legacy_seed_db_path: Optional[str] = None
    animals: list[AnimalInfo] = field(default_factory=list)

    def ensure_animals(self) -> None:
        """Ensure animals list has at least ``num_animals`` entries."""
        while len(self.animals) < self.num_animals:
            self.animals.append(AnimalInfo(animal_id=str(1000 + len(self.animals))))


@dataclass
class FallbackTrackingConfig:
    """Backup tracking parameters shared by acquisition tasks."""

    min_area: int = 80
    max_area: int = 0
    morph_kernel_size: int = 5
    max_jump_px: float = 0.0
    selection_mode: str = "closest_else_largest"
    min_circularity: float = 0.0
    range_low: int = 0
    range_high: int = 255
    node_max_jump_px: float = 0.0
    node_jump_confirm_frames: int = 2
    min_sleap_nodes: int = 1
    show_blob_overlay: bool = True
    max_contours: int = 0


@dataclass
class AcquisitionConfig:
    """Shared acquisition shell configuration independent of task geometry."""

    session: SessionConfig = field(default_factory=SessionConfig)
    output_dir: Optional[str] = None
    h5_filename: str = "trials.h5"
    arena_type: str = ""
    run_mode: str = "continuous"
    fallback_tracking: FallbackTrackingConfig = field(
        default_factory=FallbackTrackingConfig
    )
    sleap_confidence_pct: int = 50
    sleap_every_n: int = 1
    sleap_exit_min_keypoints: int = 2
    fallback_exit_blob_overlap_pct: float = 15.0
    track_exit_either_success: bool = False
    sleap_model_path: str = ""
    track_show: bool = True
    track_async: bool = False
    track_enable_backup: bool = True
    track_enable_sleap: bool = True
    # Linear scale applied to width/height before SLEAP/backup inference (1.0 = full res, 0.5 = half).
    track_infer_scale: float = 1.0
    overlay_opacity_pct: int = 70
    arduino_port: Optional[str] = None
    run_analysis_after_trial: bool = False
