"""condition_labels_csv helpers (Phase C C6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maze.pipeline.io.file_discovery import CONDITION_LABELS_HEADER
from maze.pipeline.condition_labels_csv import (
    ConditionLabelsCsvError,
    create_condition_labels_csv,
    validate_condition_labels_csv,
)


def test_create_condition_labels_csv_writes_header(tmp_path: Path) -> None:
    p = tmp_path / "condition_labels.csv"
    out = create_condition_labels_csv(p)
    assert out == p.resolve()
    validate_condition_labels_csv(p)
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == ",".join(CONDITION_LABELS_HEADER)


def test_create_refuses_existing_without_overwrite(tmp_path: Path) -> None:
    p = tmp_path / "condition_labels.csv"
    create_condition_labels_csv(p)
    with pytest.raises(ConditionLabelsCsvError, match="already exists"):
        create_condition_labels_csv(p, overwrite=False)


def test_create_overwrite_existing(tmp_path: Path) -> None:
    p = tmp_path / "condition_labels.csv"
    p.write_text("bad\n", encoding="utf-8")
    create_condition_labels_csv(p, overwrite=True)
    validate_condition_labels_csv(p)


def test_validate_rejects_wrong_header(tmp_path: Path) -> None:
    p = tmp_path / "bad.csv"
    p.write_text("animal_id,sex\n1,M\n", encoding="utf-8")
    with pytest.raises(ConditionLabelsCsvError, match="header mismatch"):
        validate_condition_labels_csv(p)


def test_validate_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConditionLabelsCsvError, match="not found"):
        validate_condition_labels_csv(tmp_path / "missing.csv")
