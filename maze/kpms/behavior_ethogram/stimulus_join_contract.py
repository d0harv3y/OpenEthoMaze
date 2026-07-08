"""Contract for stimulus ↔ bout join artifacts (pilot MI analysis).

Documented in ``docs/stimulus_mi_contract.md`` (schema id ``stimulus_join_v1``).
"""

from __future__ import annotations

from dataclasses import dataclass

from maze.kpms.manifest_subset import STRATIFY_LABEL_COLUMNS

STIMULUS_JOIN_SCHEMA_VERSION = "stimulus_join_v1"

STIMULUS_BOUT_IDENTITY_FIELDS: tuple[str, ...] = (
    "stream",
    "seed",
    "trial_key",
    *STRATIFY_LABEL_COLUMNS,
    "raw_syllable_id",
    "bout_index",
    "row_start",
    "row_end_exclusive",
    "bout_frames",
    "bout_duration_s",
    "bout_primary_state",
)

STIMULUS_SCALAR_FIELDS: tuple[str, ...] = (
    "bout_mean_duty",
    "bout_mean_dist_px",
)

STIMULUS_BOUT_TABLE_FIELDS: tuple[str, ...] = (
    *STIMULUS_BOUT_IDENTITY_FIELDS,
    *STIMULUS_SCALAR_FIELDS,
)

ALLOWED_GENOTYPE_STRAINS: frozenset[str] = frozenset({"wt", "tg"})


@dataclass(frozen=True)
class StimulusFieldSpec:
    name: str
    units: str
    description: str


STIMULUS_SCALAR_FIELD_SPECS: tuple[StimulusFieldSpec, ...] = (
    StimulusFieldSpec(
        "bout_mean_duty",
        "0–1",
        "Mean delivered motor PWM duty (``feedback/table.motor_fb``) over bout kpMS rows.",
    ),
    StimulusFieldSpec(
        "bout_mean_dist_px",
        "px",
        "Mean distance-to-exit (``ambulation_metrics/*/xy.dist_to_exit_px``) over bout kpMS rows.",
    ),
)


def assert_stimulus_join_contract_in_sync() -> None:
    if tuple(STIMULUS_SCALAR_FIELD_SPECS[i].name for i in range(len(STIMULUS_SCALAR_FIELD_SPECS))) != STIMULUS_SCALAR_FIELDS:
        raise AssertionError("STIMULUS_SCALAR_FIELD_SPECS must match STIMULUS_SCALAR_FIELDS")
