"""Syllable-sequence grammar contract (Option A / S3).

Authority for rule schema and candidate CSV columns.
Documented in ``docs/grammar_rule_contract.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

GRAMMAR_RULES_SCHEMA_VERSION = "grammar_rules_v1"
GRAMMAR_CANDIDATE_EXEMPLARS_SCHEMA = "grammar_candidate_exemplars_v1"

ANCHOR_BUCKETS: frozenset[str] = frozenset({"moving", "still", "ignore"})

# Speed gray zone for overlay gate (m/s).
OVERLAY_SPEED_GRAY_LO_MPS = 0.06
OVERLAY_SPEED_GRAY_HI_MPS = 0.14
OVERLAY_LOW_SPEED_MPS = 0.06
OVERLAY_HIGH_DHEADING = 0.25

CANDIDATE_SEQUENCE_FIELDS: tuple[str, ...] = (
    "pattern_json",
    "pattern_len",
    "count",
    "n_trials",
    "mean_speed_mps",
    "mean_abs_dheading",
    "mean_straightness",
    "mean_blob_area_px2",
    "must_review_overlay",
    "behavior_name",
    "anchor_bucket",
    "reviewed_at",
    "reviewed_trial_key",
    "notes",
)


@dataclass(frozen=True)
class CandidateFieldSpec:
    name: str
    description: str


CANDIDATE_FIELD_SPECS: tuple[CandidateFieldSpec, ...] = (
    CandidateFieldSpec("pattern_json", "JSON list of raw syllable ids, e.g. ``[3, 7, 7]``."),
    CandidateFieldSpec("pattern_len", "Length of the syllable-id pattern (bout n-gram order)."),
    CandidateFieldSpec("count", "Total occurrences across mined trials."),
    CandidateFieldSpec("n_trials", "Number of distinct trials containing the pattern."),
    CandidateFieldSpec("mean_speed_mps", "Pooled mean bout speed over pattern matches (m/s)."),
    CandidateFieldSpec("mean_abs_dheading", "Pooled mean |dheading| over pattern matches."),
    CandidateFieldSpec("mean_straightness", "Pooled mean straightness over pattern matches."),
    CandidateFieldSpec("mean_blob_area_px2", "Pooled mean blob area over pattern matches."),
    CandidateFieldSpec(
        "must_review_overlay",
        "1 when exemplar overlay review is required before naming.",
    ),
    CandidateFieldSpec(
        "behavior_name",
        "Human-curated portable behavior name; empty until curated.",
    ),
    CandidateFieldSpec(
        "anchor_bucket",
        "Harness tag: ``moving``, ``still``, or ``ignore`` (per behavior_name).",
    ),
    CandidateFieldSpec("reviewed_at", "ISO timestamp after exemplar overlay review."),
    CandidateFieldSpec("reviewed_trial_key", "Trial key watched during overlay review."),
    CandidateFieldSpec("notes", "Optional curator notes."),
)


def normalize_anchor_bucket(raw: str) -> str:
    bucket = str(raw).strip().lower()
    if bucket not in ANCHOR_BUCKETS:
        raise ValueError(f"anchor_bucket must be one of {sorted(ANCHOR_BUCKETS)}; got {raw!r}")
    return bucket


def assert_grammar_contract_in_sync() -> None:
    names = [s.name for s in CANDIDATE_FIELD_SPECS]
    if tuple(names) != CANDIDATE_SEQUENCE_FIELDS:
        raise AssertionError("CANDIDATE_FIELD_SPECS must match CANDIDATE_SEQUENCE_FIELDS order")
