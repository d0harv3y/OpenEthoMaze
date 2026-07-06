"""Behavior token labels CSV contract (Stage III curation).

Documented in ``docs/behavior_token_review_contract.md``.
"""

from __future__ import annotations

BEHAVIOR_TOKEN_LABELS_SCHEMA = "behavior_token_labels_v1"

BEHAVIOR_TOKEN_LABEL_FIELDS: tuple[str, ...] = (
    "behavior_token",
    "token_n_bouts",
    "token_mean_speed_mps",
    "token_mean_abs_dheading",
    "locomotion_tier",
    "behavior_name",
    "anchor_bucket",
    "reviewed_at",
    "reviewed_trial_key",
    "notes",
)

CURATED_BEHAVIOR_TOKEN_LABEL_FIELDS: frozenset[str] = frozenset(
    {
        "behavior_name",
        "anchor_bucket",
        "reviewed_at",
        "reviewed_trial_key",
        "notes",
    }
)

REFERENCE_BEHAVIOR_TOKEN_LABEL_FIELDS: frozenset[str] = frozenset(
    set(BEHAVIOR_TOKEN_LABEL_FIELDS) - CURATED_BEHAVIOR_TOKEN_LABEL_FIELDS
)
