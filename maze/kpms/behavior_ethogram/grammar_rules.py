"""Syllable-sequence grammar rules: I/O and bout-level application."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from maze.kpms.io import write_json

from .grammar_contract import GRAMMAR_RULES_SCHEMA_VERSION
from .grammar_enrich import validate_curated_candidate_rows
from .grammar_mine import read_candidate_sequences_csv


@dataclass(frozen=True)
class GrammarRule:
    pattern: tuple[int, ...]
    behavior_name: str
    priority: int = 0


@dataclass(frozen=True)
class GrammarRules:
    fit_id: str
    rules: tuple[GrammarRule, ...]
    schema: str = GRAMMAR_RULES_SCHEMA_VERSION
    behavior_anchor_buckets: Mapping[str, str] = field(default_factory=dict)

    def behavior_names(self) -> tuple[str, ...]:
        names = sorted({r.behavior_name for r in self.rules})
        return tuple(names)


def _parse_pattern(raw: Any) -> tuple[int, ...]:
    if isinstance(raw, str):
        parsed = json.loads(raw)
    else:
        parsed = raw
    if not isinstance(parsed, (list, tuple)) or not parsed:
        raise ValueError("pattern must be a non-empty list of syllable ids")
    return tuple(int(x) for x in parsed)


def grammar_rule_from_mapping(row: Mapping[str, Any]) -> GrammarRule:
    pattern = _parse_pattern(row["pattern"])
    name = str(row["behavior_name"]).strip()
    if not name:
        raise ValueError("behavior_name is required for grammar rules")
    priority = int(row.get("priority", 0))
    return GrammarRule(pattern=pattern, behavior_name=name, priority=priority)


def grammar_rules_to_json_dict(doc: GrammarRules) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": doc.schema,
        "fit_id": doc.fit_id,
        "rules": [
            {
                "pattern": list(r.pattern),
                "behavior_name": r.behavior_name,
                "priority": int(r.priority),
            }
            for r in doc.rules
        ],
    }
    if doc.behavior_anchor_buckets:
        payload["behavior_anchor_buckets"] = {
            str(k): str(v) for k, v in doc.behavior_anchor_buckets.items()
        }
    return payload


def write_grammar_rules_json(path: Path | str, doc: GrammarRules) -> None:
    write_json(Path(path), grammar_rules_to_json_dict(doc))


def read_grammar_rules_json(path: Path | str) -> GrammarRules:
    with Path(path).open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"grammar rules must be a JSON object: {path}")
    schema = str(raw.get("schema", ""))
    if schema != GRAMMAR_RULES_SCHEMA_VERSION:
        raise ValueError(f"unsupported grammar rules schema {schema!r} in {path}")
    fit_id = str(raw.get("fit_id", "")).strip()
    if not fit_id:
        raise ValueError(f"fit_id required in grammar rules: {path}")
    rules_raw = raw.get("rules")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise ValueError(f"rules must be a non-empty list in {path}")
    rules = tuple(grammar_rule_from_mapping(r) for r in rules_raw)
    buckets_raw = raw.get("behavior_anchor_buckets", {})
    buckets: dict[str, str] = {}
    if isinstance(buckets_raw, dict):
        buckets = {str(k): str(v) for k, v in buckets_raw.items()}
    return GrammarRules(fit_id=fit_id, rules=rules, behavior_anchor_buckets=buckets)


def rules_from_curated_candidates(
    candidates_csv: Path | str,
    *,
    fit_id: str,
    force: bool = False,
) -> GrammarRules:
    """Build rules from candidate rows with non-empty ``behavior_name``."""
    rows = read_candidate_sequences_csv(candidates_csv)
    behavior_anchor_buckets = validate_curated_candidate_rows(rows, force=force)
    rules: list[GrammarRule] = []
    for row in rows:
        name = str(row.get("behavior_name", "")).strip()
        if not name:
            continue
        pat = _parse_pattern(row["pattern_json"])
        priority = len(pat) * 10
        rules.append(GrammarRule(pattern=pat, behavior_name=name, priority=priority))
    if not rules:
        raise ValueError(f"no curated rows with behavior_name in {candidates_csv}")
    rules.sort(key=lambda r: (-len(r.pattern), -r.priority))
    return GrammarRules(
        fit_id=fit_id,
        rules=tuple(rules),
        behavior_anchor_buckets=behavior_anchor_buckets,
    )


def _rule_sort_key(rule: GrammarRule) -> tuple[int, int, tuple[int, ...]]:
    return (-len(rule.pattern), -int(rule.priority), rule.pattern)


def label_bouts_with_grammar(
    bout_syllable_ids: Sequence[int],
    rules: Sequence[GrammarRule],
) -> list[str | None]:
    """Greedy longest-pattern match over bout-level syllable ids."""
    n = len(bout_syllable_ids)
    out: list[str | None] = [None] * n
    if n == 0 or not rules:
        return out
    ordered = sorted(rules, key=_rule_sort_key)
    i = 0
    while i < n:
        matched = False
        for rule in ordered:
            pat = rule.pattern
            span = len(pat)
            if i + span > n:
                continue
            if tuple(int(bout_syllable_ids[i + j]) for j in range(span)) == pat:
                for j in range(i, i + span):
                    out[j] = rule.behavior_name
                i += span
                matched = True
                break
        if not matched:
            i += 1
    return out


def behavior_name_to_id_map(names: Sequence[str]) -> dict[str, int]:
    ordered = sorted({str(n).strip() for n in names if str(n).strip()})
    return {name: idx for idx, name in enumerate(ordered)}
