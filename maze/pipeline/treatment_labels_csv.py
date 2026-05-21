"""Create and validate ``treatment_labels.csv`` (Phase C6)."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

from .io.file_discovery import TREATMENT_LABELS_HEADER

# Re-export for GUI/docs
CANONICAL_TREATMENT_LABELS_HEADER: tuple[str, ...] = tuple(TREATMENT_LABELS_HEADER)


class TreatmentLabelsCsvError(ValueError):
    """Invalid or missing treatment labels CSV."""


def validate_treatment_labels_csv(path: Path | str) -> None:
    """
    Ensure *path* exists and its header matches :data:`TREATMENT_LABELS_HEADER`.

    Raises:
        TreatmentLabelsCsvError: Missing file or wrong header.
    """
    p = Path(path)
    if not p.is_file():
        raise TreatmentLabelsCsvError(f"Treatment labels file not found: {p}")

    with p.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise TreatmentLabelsCsvError(f"Treatment labels CSV is empty: {p}") from exc

    if list(header) != list(TREATMENT_LABELS_HEADER):
        raise TreatmentLabelsCsvError(
            f"Treatment labels header mismatch in {p}.\n"
            f"  Expected: {list(TREATMENT_LABELS_HEADER)}\n"
            f"  Found:    {header}"
        )


def create_treatment_labels_csv(
    path: Path | str,
    *,
    overwrite: bool = False,
) -> Path:
    """
    Write a new CSV with only the canonical header row.

    Raises:
        TreatmentLabelsCsvError: Target exists and *overwrite* is false.
    """
    p = Path(path)
    if p.exists() and not overwrite:
        raise TreatmentLabelsCsvError(
            f"Treatment labels file already exists: {p}. "
            "Choose overwrite or pick another path."
        )
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(TREATMENT_LABELS_HEADER))
        writer.writeheader()
    return p.resolve()


def open_treatment_labels_in_system_editor(path: Path | str) -> None:
    """
    Open *path* with the OS default application for CSV files.

    Raises:
        TreatmentLabelsCsvError: File missing or open failed.
    """
    p = Path(path).resolve()
    validate_treatment_labels_csv(p)
    try:
        if sys.platform == "win32":
            os.startfile(p)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)], check=True)
        else:
            subprocess.run(["xdg-open", str(p)], check=True)
    except OSError as exc:
        raise TreatmentLabelsCsvError(f"Could not open {p} in system editor: {exc}") from exc
