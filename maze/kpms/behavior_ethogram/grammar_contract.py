"""Syllable-sequence grammar contract (Option A / S3).

Authority for rule schema and candidate CSV columns.
Documented in ``docs/grammar_rule_contract.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

GRAMMAR_RULES_SCHEMA_VERSION = "grammar_rules_v1"

CANDIDATE_SEQUENCE_FIELDS: tuple[str, ...] = (
    "pattern_json",
    "pattern_len",
    "count",
    "n_trials",
    "example_trial_keys",
    "behavior_name",
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
    CandidateFieldSpec(
        "example_trial_keys",
        "Semicolon-separated trial keys for exemplar review (up to 5).",
    ),
    CandidateFieldSpec(
        "behavior_name",
        "Human-curated portable behavior name; empty until curated.",
    ),
    CandidateFieldSpec("notes", "Optional curator notes."),
)


def assert_grammar_contract_in_sync() -> None:
    names = [s.name for s in CANDIDATE_FIELD_SPECS]
    if tuple(names) != CANDIDATE_SEQUENCE_FIELDS:
        raise AssertionError("CANDIDATE_FIELD_SPECS must match CANDIDATE_SEQUENCE_FIELDS")
