"""Controller-first discovery defaults (acquisition output_dir + trials.h5)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from maze.controller.acquisition.shared_config import AcquisitionConfig


def default_results_h5_path(config: "AcquisitionConfig") -> Path:
    """``<output_dir>/<h5_filename>`` from acquisition settings."""
    out = (config.output_dir or "").strip()
    name = (config.h5_filename or "trials.h5").strip() or "trials.h5"
    if Path(name).name != name:
        name = Path(name).name
    return Path(out) / name if out else Path(name)


def default_discovery_data_dirs(config: "AcquisitionConfig") -> Optional[list[Path]]:
    """
    Data roots to scan for videos and pose files.

    Controller-first: acquisition ``output_dir`` only. Falls back to ``None`` so
    :func:`maze.pipeline.io.file_discovery.discover_trials` uses ``paths.DATA_DIRS``.
    """
    out = (config.output_dir or "").strip()
    if not out:
        return None
    return [Path(out)]


def default_treatment_labels_path(config: "AcquisitionConfig") -> Path:
    """Prefer ``<output_dir>/treatment_labels.csv``; else repo ``inputs/treatment_labels.csv``."""
    out = (config.output_dir or "").strip()
    if out:
        return Path(out) / "treatment_labels.csv"
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "inputs" / "treatment_labels.csv"
