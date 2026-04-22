from __future__ import annotations

from dataclasses import dataclass, field

from ..shared_config import AcquisitionConfig
from ....core.tasks import ARENA_TYPE_RADIAL_ARM


def ram_apothem_cm_from_template(template: RadialArmTemplateConfig) -> float:
    """Half of center mid-edge span; apothem of the hub 16-gon in cm."""
    return float(template.center_midedge_to_midedge_cm) / 2.0


def ram_derived_px_per_cm(template: RadialArmTemplateConfig, calibration: RadialArmCalibrationConfig) -> float:
    """pixels per cm from hub apothem knob and physical print size (VAST-style ratio)."""
    ap_cm = ram_apothem_cm_from_template(template)
    ap_px = float(calibration.apothem_px)
    if ap_cm > 0.0 and ap_px > 0.0:
        return ap_px / ap_cm
    return 0.0


def sync_ram_px_per_cm(ram: RadialArmTaskConfig) -> None:
    """Write derived scale into ``calibration.px_per_cm`` for H5 / pipeline consumers."""
    ram.calibration.px_per_cm = ram_derived_px_per_cm(ram.template, ram.calibration)


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
    #: Hub apothem in **image pixels** (distance center → flat side). Paired with
    #: ``center_midedge_to_midedge_cm`` to derive ``px_per_cm`` (read-only ratio).
    apothem_px: float = 0.0
    #: Denormalized scale for HDF5 / legacy readers; kept in sync by :func:`sync_ram_px_per_cm`.
    px_per_cm: float = 0.0
    #: Extra margin (px) around template bbox for tracking crop; ``0`` = use 20% of half-extent.
    tracking_mask_margin_px: float = 0.0
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
