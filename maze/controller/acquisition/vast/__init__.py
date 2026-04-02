"""VAST task-local acquisition modules."""

from .config import (
    ArenaConfig,
    ExitAngleConfig,
    FT_TO_CM,
    M_TO_CM,
    StimulusConfig,
    VastControllerConfig,
    VastTaskConfig,
)
from ..shared_config import AnimalInfo, FallbackTrackingConfig, SessionConfig
from .trial_flow import (
    OverlayInfo,
    Phase,
    TrialController,
    TrialMode,
    TrialState,
    TrialStateMachine,
    parse_phase_mode_from_config,
)

VastOverlayInfo = OverlayInfo
VastPhase = Phase
VastTrialController = TrialController
VastTrialMode = TrialMode
VastTrialState = TrialState
VastTrialStateMachine = TrialStateMachine
parse_vast_phase_mode_from_config = parse_phase_mode_from_config

__all__ = [
    "AnimalInfo",
    "ArenaConfig",
    "VastControllerConfig",
    "VastTaskConfig",
    "ExitAngleConfig",
    "FallbackTrackingConfig",
    "FT_TO_CM",
    "M_TO_CM",
    "SessionConfig",
    "StimulusConfig",
    "OverlayInfo",
    "Phase",
    "TrialController",
    "TrialMode",
    "TrialState",
    "TrialStateMachine",
    "parse_phase_mode_from_config",
    "VastOverlayInfo",
    "VastPhase",
    "VastTrialController",
    "VastTrialMode",
    "VastTrialState",
    "VastTrialStateMachine",
    "parse_vast_phase_mode_from_config",
]
