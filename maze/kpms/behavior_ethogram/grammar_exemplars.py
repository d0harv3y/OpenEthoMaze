"""Sidecar I/O for grammar candidate exemplars (S3.2+).

Verbose review fields live in ``candidate_exemplars.json``, not ``candidate_sequences.csv``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from maze.kpms.io import write_json

from .grammar_contract import GRAMMAR_CANDIDATE_EXEMPLARS_SCHEMA
from .grammar_matches import PatternMatch, parse_example_matches_json
from .grammar_mine import MinedSequence

PATTERN_KEY_FIELDS = ("example_trial_keys", "example_matches")


@dataclass(frozen=True)
class PatternExemplars:
    example_trial_keys: tuple[str, ...]
    example_matches: tuple[PatternMatch, ...]


def pattern_json_key(pattern: tuple[int, ...]) -> str:
    return json.dumps(list(pattern))


def exemplars_from_candidate(cand: MinedSequence) -> PatternExemplars:
    matches = parse_example_matches_json(cand.example_matches_json)
    return PatternExemplars(
        example_trial_keys=cand.example_trial_keys,
        example_matches=matches,
    )


def exemplars_doc_to_json_dict(
    candidates: Sequence[MinedSequence],
    *,
    fit_id: str,
) -> dict[str, Any]:
    patterns: dict[str, Any] = {}
    for cand in candidates:
        ex = exemplars_from_candidate(cand)
        if not ex.example_trial_keys and not ex.example_matches:
            continue
        key = pattern_json_key(cand.pattern)
        patterns[key] = {
            "example_trial_keys": list(ex.example_trial_keys),
            "example_matches": [m.to_dict() for m in ex.example_matches],
        }
    return {
        "schema": GRAMMAR_CANDIDATE_EXEMPLARS_SCHEMA,
        "fit_id": fit_id,
        "patterns": patterns,
    }


def write_candidate_exemplars_json(
    path: Path | str,
    candidates: Sequence[MinedSequence],
    *,
    fit_id: str,
) -> None:
    write_json(Path(path), exemplars_doc_to_json_dict(candidates, fit_id=fit_id))


def read_candidate_exemplars_json(path: Path | str) -> dict[str, PatternExemplars]:
    with Path(path).open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"candidate exemplars must be a JSON object: {path}")
    schema = str(raw.get("schema", ""))
    if schema != GRAMMAR_CANDIDATE_EXEMPLARS_SCHEMA:
        raise ValueError(f"unsupported exemplars schema {schema!r} in {path}")
    patterns_raw = raw.get("patterns", {})
    if not isinstance(patterns_raw, dict):
        raise ValueError(f"patterns must be an object in {path}")
    out: dict[str, PatternExemplars] = {}
    for key, entry in patterns_raw.items():
        if not isinstance(entry, dict):
            continue
        keys_raw = entry.get("example_trial_keys", [])
        matches_raw = entry.get("example_matches", [])
        trial_keys = tuple(str(k) for k in keys_raw) if isinstance(keys_raw, list) else ()
        matches = (
            tuple(PatternMatch.from_dict(m) for m in matches_raw)
            if isinstance(matches_raw, list)
            else ()
        )
        out[str(key)] = PatternExemplars(example_trial_keys=trial_keys, example_matches=matches)
    return out


def exemplars_for_pattern(
    doc: Mapping[str, PatternExemplars],
    pattern_json: str,
) -> PatternExemplars | None:
    return doc.get(str(pattern_json).strip())


def exemplars_from_legacy_csv_row(row: Mapping[str, str]) -> PatternExemplars:
    """Fallback when only legacy CSV columns exist."""
    keys_raw = str(row.get("example_trial_keys", "")).strip()
    trial_keys = tuple(k for k in keys_raw.split(";") if k)
    matches = parse_example_matches_json(str(row.get("example_matches_json", "")))
    return PatternExemplars(example_trial_keys=trial_keys, example_matches=matches)


def load_pattern_exemplars(
    grammar_dir: Path | str,
    pattern_json: str,
    *,
    candidates_row: Mapping[str, str] | None = None,
) -> PatternExemplars:
    """Load exemplars from sidecar, with optional legacy CSV fallback."""
    from .paths import grammar_candidate_exemplars_json

    sidecar = grammar_candidate_exemplars_json(grammar_dir)
    if sidecar.is_file():
        doc = read_candidate_exemplars_json(sidecar)
        found = exemplars_for_pattern(doc, pattern_json)
        if found is not None:
            return found
    if candidates_row is not None:
        legacy = exemplars_from_legacy_csv_row(candidates_row)
        if legacy.example_trial_keys or legacy.example_matches:
            return legacy
    return PatternExemplars(example_trial_keys=(), example_matches=())
