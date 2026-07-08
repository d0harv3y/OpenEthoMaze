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
