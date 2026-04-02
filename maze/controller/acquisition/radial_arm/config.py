from __future__ import annotations

from dataclasses import dataclass, field

from ..shared_config import AcquisitionConfig
from ....core.tasks import ARENA_TYPE_RADIAL_ARM


@dataclass
class RadialArmTemplateConfig:
    """Canonical template parameters for the radial-arm maze."""

    center_midedge_to_midedge_cm: float = 80.0
    arm_length_cm: float = 55.0
    arm_width_cm: float = 15.0
    arm_split_cm: float = 27.5
    hole_arm_index: int = 0
    hole_radius_cm: float = 5.0
    hole_inset_from_arm_end_cm: float = 10.0


@dataclass
class RadialArmCalibrationConfig:
    """Session-editable placement of the RAM template in image space."""

    template_center_x_px: float = 0.0
    template_center_y_px: float = 0.0
    template_rotation_deg: float = 0.0
    px_per_cm: float = 0.0
    edit_region_name: str = ""


@dataclass
class RadialArmTaskConfig:
    """Task-local RAM settings kept alongside the shared controller fields."""

    template: RadialArmTemplateConfig = field(default_factory=RadialArmTemplateConfig)
    calibration: RadialArmCalibrationConfig = field(default_factory=RadialArmCalibrationConfig)
    exit_arm_index: int = 0
    rewarded_arm_index: int = 0
    speaker_device_name: str = ""
    speaker_volume_pct: float = 100.0
    stimulus_frequency_hz: float = 5000.0
    stimulus_enabled: bool = False


@dataclass
class RadialArmControllerConfig(AcquisitionConfig):
    """RAM controller config with shared acquisition fields plus task-local settings."""

    h5_filename: str = "ram_trials.h5"
    arena_type: str = ARENA_TYPE_RADIAL_ARM
    radial_arm: RadialArmTaskConfig = field(default_factory=RadialArmTaskConfig)

    @property
    def run_phase(self) -> str:
        """Compatibility shim while shared UI still expects a phase-like label."""
        return "radial_arm"

    @run_phase.setter
    def run_phase(self, value: str) -> None:
        del value
