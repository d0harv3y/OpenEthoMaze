"""
Configuration and arena model for the circular open field controller.

Arena: circular, diameter in feet; center = inner circle (center_pct of diameter);
edge = annulus. Exit target in center region, angles from Latin square.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Feet to cm (for arena diameter)
FT_TO_CM = 30.48
M_TO_CM = 100.0


@dataclass
class ArenaConfig:
    """Arena geometry and calibration. Diameter stored in cm; px_per_cm derived from ROI radius."""

    diameter_cm: float = 121.92  # 4 ft default
    diameter_display_unit: str = "ft"  # "ft" or "m" for UI display
    radius_px: float = 0.0  # arena circle radius in pixels (from ROI); used to derive px_per_cm and draw ROI
    tracking_radius_px: float = 0.0  # mask radius for tracking; 0 = use radius_px (same as ROI)
    center_pct: float = 0.5  # center circle diameter = center_pct * arena diameter
    exit_radius_cm: float = 5.0
    arena_center_x_px: float = 0.0
    arena_center_y_px: float = 0.0

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

    # Default multiplier when tracking_radius_px is 0 (tracking region larger than calibration ROI)
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
    offset_deg: float = -30.0  # first angle relative to opposite
    step_deg: float = 20.0  # angle_i = offset_deg + i * step_deg

    def angle_deg(self, index: int) -> float:
        """Return angle in degrees for exit index 0..n_angles-1."""
        if index < 0 or index >= self.n_angles:
            raise IndexError(f"Exit index must be 0..{self.n_angles - 1}")
        return self.offset_deg + index * self.step_deg

    def all_angles_deg(self) -> list[float]:
        return [self.angle_deg(i) for i in range(self.n_angles)]


@dataclass
class StimulusConfig:
    """Stimulus (vibration) duty limits and polarity. Duty mapping is in TrialStateMachine.duty_for_position."""

    min_at_exit: bool = True  # True = colder (min duty when at exit)
    min_duty_pct: float = 35.0
    max_duty_pct: float = 85.0


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
    """Session and trial counts; animal list; timing. Session identity is by user-entered session_id (state machine / profile)."""

    num_animals: int = 1
    num_trials: int = 9
    max_trial_duration_s: float = 120.0
    iti_s: float = 10.0
    seed: Optional[int] = None
    animals: list[AnimalInfo] = field(default_factory=list)

    def ensure_animals(self) -> None:
        """Ensure animals list has at least num_animals entries."""
        while len(self.animals) < self.num_animals:
            self.animals.append(
                AnimalInfo(animal_id=str(1000 + len(self.animals)))
            )


@dataclass
class FallbackTrackingConfig:
    """Parameters for the backup (in-range threshold + morphology) tracker when SLEAP is unavailable or low confidence."""

    min_area: int = 80  # minimum contour area (px) to count as a blob
    max_area: int = 0  # maximum contour area (px); 0 = no limit (reject huge blobs if set)
    morph_kernel_size: int = 5  # morphology ellipse kernel size (odd)
    max_jump_px: float = 0.0  # if > 0, reject closest blob if farther than this from last position
    selection_mode: str = "closest_else_largest"  # "largest" | "closest" | "closest_else_largest"
    min_circularity: float = 0.0  # 0 = off; filter contours with 4*pi*area/perim^2 below this (0..1)
    range_low: int = 0  # intensity range threshold: min (0-255); pixel on if range_low <= intensity <= range_high
    range_high: int = 255  # intensity range threshold: max (0-255)
    node_max_jump_px: float = 0.0  # SLEAP nodes: 0 = off; invalidate node if it moves more than this from previous frame
    min_sleap_nodes: int = 1  # SLEAP: use backup tracker if fewer than this many nodes pass confidence threshold
    # When True, build and draw the fallback blob mask overlay (green tint where blob detected). Disable for better FPS.
    show_blob_overlay: bool = True
    # Max contours to consider per frame (0 = no limit). Keeps largest by area; can reduce FPS drops when many in-range pixels.
    max_contours: int = 0


@dataclass
class ControllerConfig:
    """Full controller profile: arena, calibration, session, stimulus, exit angles."""

    arena: ArenaConfig = field(default_factory=ArenaConfig)
    exit_angles: ExitAngleConfig = field(default_factory=ExitAngleConfig)
    stimulus: StimulusConfig = field(default_factory=StimulusConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    # Habituation training: constant duty when in edge
    hab_training_duty_pct: float = 60.0
    # VAST / habituation_training: stimulus intensity during wait_not_center (default 0)
    wait_not_center_duty_pct: float = 0.0
    # Output base directory for H5 and per-trial videos (persisted in profile)
    output_dir: Optional[str] = None
    # H5 database filename inside output_dir (e.g. trials.h5)
    h5_filename: str = "trials.h5"
    # Phase (stimulus/exit behaviour) and mode (trial ordering).
    run_phase: str = "habituation"  # habituation | habituation_training | VAST
    run_mode: str = "continuous"    # continuous | alternating (trial order)

    # Backup (fallback) tracking: in-range threshold + morphology
    fallback_tracking: FallbackTrackingConfig = field(default_factory=FallbackTrackingConfig)
    # SLEAP: per-node confidence threshold (0–100 %); run model every N frames (1=every frame)
    sleap_confidence_pct: int = 50
    sleap_every_n: int = 1
    # SLEAP model directory (single-instance; empty = backup tracker only)
    sleap_model_path: str = ""
    # Tracking display/behavior (moved from main GUI to Settings → Tracking)
    track_show: bool = True
    track_async: bool = False
    track_backup_only: bool = False
    overlay_opacity_pct: int = 70
    # MC (Arduino) serial port for vibration stimulus; empty = not set
    arduino_port: Optional[str] = None
    # Run VAST pipeline analysis (metrics, heatmap, movement bouts) after each trial completes.
    run_analysis_after_trial: bool = False
