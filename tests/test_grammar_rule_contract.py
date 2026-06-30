"""Contract sync tests for Option A grammar artifacts."""

from __future__ import annotations

from pathlib import Path

from maze.kpms.behavior_ethogram import grammar_contract as contract
from maze.kpms.behavior_ethogram.grammar_mine import write_candidate_sequences_csv


def test_grammar_contract_internal_sync() -> None:
    contract.assert_grammar_contract_in_sync()


def test_doc_pins_schema_version() -> None:
    doc = Path(__file__).resolve().parents[1] / "docs" / "grammar_rule_contract.md"
    content = doc.read_text(encoding="utf-8")
    assert contract.GRAMMAR_RULES_SCHEMA_VERSION in content
    assert "grammar_contract.py" in content


def test_candidate_csv_uses_contract_fields(tmp_path) -> None:
    from maze.kpms.behavior_ethogram.grammar_mine import MinedSequence

    path = tmp_path / "c.csv"
    write_candidate_sequences_csv(
        path,
        [MinedSequence(pattern=(1, 2), count=3, n_trials=2, example_trial_keys=("t1",))],
    )
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert header == ",".join(contract.CANDIDATE_SEQUENCE_FIELDS)
