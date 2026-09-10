"""CSV schemas for behavior-token summarize outputs."""

from __future__ import annotations

BEHAVIOR_TOKEN_SUMMARIZE_SCHEMA = "behavior_token_summarize_v1"

OCCUPANCY_FIELDS: tuple[str, ...] = (
    "grain",
    "label",
    "interval",
    "session",
    "condition",
    "sex",
    "strain",
    "occupancy_fraction",
    "label_duration_s",
    "interval_duration_s",
    "n_trials",
    "n_animals",
)

TRANSITION_FIELDS: tuple[str, ...] = (
    "grain",
    "label_i",
    "label_j",
    "interval",
    "session",
    "condition",
    "sex",
    "strain",
    "transition_count",
    "transition_rate",
    "n_trials",
    "n_animals",
)
