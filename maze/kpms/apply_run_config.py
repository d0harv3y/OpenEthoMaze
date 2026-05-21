"""kpMS apply job configuration (no keypoint_moseq import — safe for CI)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class KpmsApplyRunConfig:
    """Inputs for a single kpMS apply job (CLI or GUI)."""

    project_dir: Path
    model_name: str
    manifest_csv: Path
    results_path: Optional[Path] = None
    animal_ids: Optional[tuple[str, ...]] = None
    sessions: Optional[tuple[str, ...]] = None
    trials: Optional[tuple[str, ...]] = None
    include_habituation: bool = False
    exclude_experimental: bool = False
    enrich_from_treatment_labels: bool = True
    num_iters: int = 100
    reindex_syllables_before_load: bool = True
    verbose: bool = True
    overwrite_results: bool = True
