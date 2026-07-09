"""Contract for stimulus-conditioned MI artifacts (pilot analysis).

Documented in ``docs/stimulus_mi_contract.md`` (schema id ``stimulus_mi_v1``).
"""

from __future__ import annotations

STIMULUS_MI_SCHEMA_VERSION = "stimulus_mi_v1"

MI_PER_ANIMAL_FIELDS: tuple[str, ...] = (
    "animal_id",
    "sex",
    "strain",
    "tx",
    "phase",
    "stim_var",
    "mi_type",
    "n_bouts",
    "H_stim",
    "H_syll",
    "mi_raw",
    "mi_mm",
    "null_circ_mean",
    "null_circ_p",
    "null_perm_mean",
    "null_perm_p",
    "iti_control_flag",
)

GROUP_MI_TEST_FIELDS: tuple[str, ...] = (
    "factor",
    "level_a",
    "level_b",
    "phase",
    "stim_var",
    "mi_type",
    "n_a",
    "n_b",
    "median_a",
    "median_b",
    "stat",
    "p",
    "test",
)

STIM_PHASES: tuple[str, ...] = ("run", "iti")
STIM_VARS: tuple[str, ...] = ("duty", "dist")
MI_TYPES: tuple[str, ...] = ("occupancy", "transition")
GROUP_FACTORS: tuple[str, ...] = ("sex", "genotype", "tx")

EARLY_LATE_K: int = 3
MIN_TRIALS_FOR_EARLY_LATE: int = 6
TRIAL_NULL_N_PERM: int = 200
NULL_CLEAR_ALPHA: float = 0.05

MI_PER_TRIAL_FIELDS: tuple[str, ...] = (
    "animal_id",
    "sex",
    "strain",
    "tx",
    "session",
    "trial",
    "trial_key",
    "trial_ord",
    "cum_run_bouts",
    "phase",
    "stim_var",
    "mi_type",
    "n_bouts",
    "H_stim",
    "H_syll",
    "mi_raw",
    "mi_mm",
    "null_circ_mean",
    "null_circ_p",
    "excess",
)

MI_TRIAL_ANIMAL_SUMMARY_FIELDS: tuple[str, ...] = (
    "animal_id",
    "sex",
    "strain",
    "tx",
    "phase",
    "stim_var",
    "mi_type",
    "n_trials",
    "mean_mi_mm",
    "median_mi_mm",
    "mean_n_bouts",
    "mean_H_stim",
    "slope_vs_trial_ord",
    "early_late_delta",
    "slope_vs_excess",
    "early_late_delta_excess",
    "null_clear_fraction",
)

GROUP_MI_WHEN_TEST_FIELDS: tuple[str, ...] = (
    "factor",
    "level_a",
    "level_b",
    "phase",
    "stim_var",
    "mi_type",
    "metric",
    "n_a",
    "n_b",
    "median_a",
    "median_b",
    "stat",
    "p",
    "test",
)

WHEN_TEST_METRICS: tuple[str, ...] = (
    "slope_vs_trial_ord",
    "early_late_delta",
    "slope_vs_excess",
    "early_late_delta_excess",
)

PRIMARY_WHEN_PHASE: str = "run"
PRIMARY_WHEN_MI_TYPE: str = "occupancy"
