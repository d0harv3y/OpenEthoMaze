"""VAST task-local acquisition modules."""

from __future__ import annotations

from importlib import import_module

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

# ``trial_flow`` is lazy-imported: ``region_code`` imports ``vast.arena`` while the
# ``vast`` package is initializing; eager ``trial_flow`` here caused a circular import
# (region_code ↔ trial_flow).

_ALIAS_TO_TRIAL_FLOW: dict[str, str] = {
    "VastOverlayInfo": "OverlayInfo",
    "VastPhase": "Phase",
    "VastTrialController": "TrialController",
    "VastTrialMode": "TrialMode",
    "VastTrialState": "TrialState",
    "VastTrialStateMachine": "TrialStateMachine",
    "parse_vast_phase_mode_from_config": "parse_phase_mode_from_config",
}

_TRIAL_FLOW_NAMES = frozenset(
    {
        "OverlayInfo",
        "Phase",
        "TrialController",
        "TrialMode",
        "TrialState",
        "TrialStateMachine",
        "parse_phase_mode_from_config",
        *_ALIAS_TO_TRIAL_FLOW,
    }
)


def __getattr__(name: str):
    if name not in _TRIAL_FLOW_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    tf = import_module(".trial_flow", __package__)
    return getattr(tf, _ALIAS_TO_TRIAL_FLOW.get(name, name))


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
