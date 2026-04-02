"""Pipeline IO helpers for legacy trial discovery and trace loading."""

from .input_h5_loader import (
    load_trial_settings,
    load_trial_data,
    load_trial,
    TrialSettings,
    TrialData,
)
from .file_discovery import (
    discover_trials,
    TrialManifest,
    DiscoveryResult,
    get_unique_animals,
    get_trials_for_animal,
)
from .sleap_loader import (
    load_sleap_file,
    load_slp_file,
    load_analysis_h5,
    apply_jump_filter,
    TraceData,
)

__all__ = [
    # Input H5 loader
    "load_trial_settings",
    "load_trial_data", 
    "load_trial",
    "TrialSettings",
    "TrialData",
    # File discovery
    "discover_trials",
    "TrialManifest",
    "DiscoveryResult",
    "get_unique_animals",
    "get_trials_for_animal",
    # SLEAP loader
    "load_sleap_file",
    "load_slp_file",
    "load_analysis_h5",
    "apply_jump_filter",
    "TraceData",
]
