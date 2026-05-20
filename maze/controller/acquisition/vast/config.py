"""
Configuration and arena model for the circular open field controller.

Arena: circular, diameter in feet; center = inner circle (center_pct of diameter);
edge = annulus. Exit target in center region, angles from Latin square.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ....core.tasks import ARENA_TYPE_CIRCULAR
from ..shared_config import AcquisitionConfig

# Feet to cm (for arena diameter)
FT_TO_CM = 30.48
M_TO_CM = 100.0


@dataclass
class ArenaConfig:
    """Arena geometry and calibration. Diameter stored in cm; px_per_cm derived from ROI radius."""

    diameter_cm: float = 121.92  # 4 ft default
    diameter_display_unit: str = "ft"  # "ft" or "m" for UI display
    radius_px: float = (
        200.0  # arena circle radius in pixels (from ROI); used to derive px_per_cm and draw ROI
    )
    tracking_radius_px: float = 250.0  # mask radius for tracking; 0 = use radius_px (same as ROI)
    center_pct: float = 0.7  # center circle diameter = center_pct * arena diameter
    exit_radius_cm: float = 12.5
    arena_center_x_px: float = 200.0
    arena_center_y_px: float = 200.0

    @property
    def diameter_ft(self) -> float:
        return self.diameter_cm / FT_TO_CM

    @property
    def diameter_m(self) -> float:
        return self.diameter_cm / M_TO_CM

    @property
    def radius_cm(self) -> float:
        return self.diameter_cm / 2.0

    @property
    def px_per_cm(self) -> float:
        """Derived from ROI radius and arena diameter: 2*radius_px/diameter_cm."""
        if self.diameter_cm > 0 and self.radius_px > 0:
            return (2.0 * self.radius_px) / self.diameter_cm
        return 2.5

    @property
    def center_radius_cm(self) -> float:
        """Radius of the inner 'center' circle."""
        return (self.diameter_cm * self.center_pct) / 2.0

    @property
    def center_radius_px(self) -> float:
        return self.center_radius_cm * self.px_per_cm

    TRACKING_RADIUS_DEFAULT_MULTIPLIER = 1.2

    @property
    def tracking_mask_radius_px(self) -> float:
        """Radius (px) for the tracking mask. If tracking_radius_px > 0 use it; else radius_px * 1.2."""
        if self.tracking_radius_px > 0:
            return self.tracking_radius_px
        return self.radius_px * self.TRACKING_RADIUS_DEFAULT_MULTIPLIER


@dataclass
class ExitAngleConfig:
    """Exit positions: n angles relative to opposite the rat, clockwise."""

    n_angles: int = 4
    offset_deg: float = -30.0
    step_deg: float = 20.0
    #: When session seed is manual: default 0-based exit angle index for new padded slots.
    default_manual_exit_index: int = 0

    def angle_deg(self, index: int) -> float:
        """Return angle in degrees for exit index 0..n_angles-1."""
        if index < 0 or index >= self.n_angles:
            raise IndexError(f"Exit index must be 0..{self.n_angles - 1}")
        return self.offset_deg + index * self.step_deg


@dataclass
class StimulusConfig:
    """Stimulus (vibration) duty limits and polarity. Duty mapping is in TrialStateMachine.duty_for_position."""

    min_at_exit: bool = True
    min_duty_pct: float = 35.0
    max_duty_pct: float = 85.0


@dataclass
class VastTaskConfig:
    """VAST-owned task payload layered on top of the shared acquisition config."""

    arena: ArenaConfig = field(default_factory=ArenaConfig)
    exit_angles: ExitAngleConfig = field(default_factory=ExitAngleConfig)
    stimulus: StimulusConfig = field(default_factory=StimulusConfig)
    run_phase: str = "habituation"
    hab_training_duty_pct: float = 60.0
    wait_not_center_duty_pct: float = 0.0


@dataclass
class VastControllerConfig(AcquisitionConfig):
    """Shared acquisition config plus the VAST-specific task payload."""

    h5_filename: str = "trials.h5"
    arena_type: str = ARENA_TYPE_CIRCULAR
    vast: VastTaskConfig = field(default_factory=VastTaskConfig)

    @property
    def arena(self) -> ArenaConfig:
        return self.vast.arena

    @arena.setter
    def arena(self, value: ArenaConfig) -> None:
        self.vast.arena = value

    @property
    def exit_angles(self) -> ExitAngleConfig:
        return self.vast.exit_angles

    @exit_angles.setter
    def exit_angles(self, value: ExitAngleConfig) -> None:
        self.vast.exit_angles = value

    @property
    def stimulus(self) -> StimulusConfig:
        return self.vast.stimulus

    @stimulus.setter
    def stimulus(self, value: StimulusConfig) -> None:
        self.vast.stimulus = value

    @property
    def run_phase(self) -> str:
        return self.vast.run_phase

    @run_phase.setter
    def run_phase(self, value: str) -> None:
        self.vast.run_phase = value

    @property
    def hab_training_duty_pct(self) -> float:
        return self.vast.hab_training_duty_pct

    @hab_training_duty_pct.setter
    def hab_training_duty_pct(self, value: float) -> None:
        self.vast.hab_training_duty_pct = value

    @property
    def wait_not_center_duty_pct(self) -> float:
        return self.vast.wait_not_center_duty_pct

    @wait_not_center_duty_pct.setter
    def wait_not_center_duty_pct(self, value: float) -> None:
        self.vast.wait_not_center_duty_pct = value
