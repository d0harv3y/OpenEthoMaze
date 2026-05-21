"""treatment_labels_csv helpers (Phase C C6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maze.pipeline.io.file_discovery import TREATMENT_LABELS_HEADER
from maze.pipeline.treatment_labels_csv import (
    TreatmentLabelsCsvError,
    create_treatment_labels_csv,
    validate_treatment_labels_csv,
)


def test_create_treatment_labels_csv_writes_header(tmp_path: Path) -> None:
    p = tmp_path / "treatment_labels.csv"
    out = create_treatment_labels_csv(p)
    assert out == p.resolve()
    validate_treatment_labels_csv(p)
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == ",".join(TREATMENT_LABELS_HEADER)


def test_create_refuses_existing_without_overwrite(tmp_path: Path) -> None:
    p = tmp_path / "treatment_labels.csv"
    create_treatment_labels_csv(p)
    with pytest.raises(TreatmentLabelsCsvError, match="already exists"):
        create_treatment_labels_csv(p, overwrite=False)


def test_create_overwrite_existing(tmp_path: Path) -> None:
    p = tmp_path / "treatment_labels.csv"
    p.write_text("bad\n", encoding="utf-8")
    create_treatment_labels_csv(p, overwrite=True)
    validate_treatment_labels_csv(p)


def test_validate_rejects_wrong_header(tmp_path: Path) -> None:
    p = tmp_path / "bad.csv"
    p.write_text("animal_id,sex\n1,M\n", encoding="utf-8")
    with pytest.raises(TreatmentLabelsCsvError, match="header mismatch"):
        validate_treatment_labels_csv(p)


def test_validate_missing_file(tmp_path: Path) -> None:
    with pytest.raises(TreatmentLabelsCsvError, match="not found"):
        validate_treatment_labels_csv(tmp_path / "missing.csv")
