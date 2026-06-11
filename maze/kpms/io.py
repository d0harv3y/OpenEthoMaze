from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ..pipeline.io.file_discovery import (
    MANIFEST_CSV_FIELDNAMES,
    TrialManifest,
    trial_manifest_csv_row_values,
)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_json_default)


def write_selected_manifest(path: Path, manifests: list[TrialManifest]) -> None:
    """Write selected trials using the same columns as the main trial manifest CSV."""
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(list(MANIFEST_CSV_FIELDNAMES))
        for m in manifests:
            writer.writerow(trial_manifest_csv_row_values(m))
