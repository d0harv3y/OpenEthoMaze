"""kpMS fit job configuration (no keypoint_moseq import — safe for CI)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .heading_idxs import PoseStream
from .manifest_subset import SubsetConfig


@dataclass(frozen=True)
class KpmsFitRunConfig:
    """Inputs for a single kpMS fit job (CLI or GUI)."""

    project_dir: Path
    model_name: str = "orm_kpms_fit"
    pose_stream: PoseStream = "anatomical"
    manifest_csv: Path | None = None
    max_trials: int = 300
    random_seed: int = 42
    include_habituation: bool = False
    exclude_experimental: bool = False
    balance_columns: tuple[str, ...] = ("sex", "tx", "phase", "strain")
    enrich_from_treatment_labels: bool = True
    force_new: bool = False
    #: float32 + ``jax_enable_x64=False`` (lower GPU memory; less numerically stable).
    use_float32: bool = False


def subset_config_from_fit_run(cfg: KpmsFitRunConfig) -> SubsetConfig:
    """Build :class:`SubsetConfig` from a fit run configuration."""
    return SubsetConfig(
        manifest_csv=Path(cfg.manifest_csv) if cfg.manifest_csv else None,
        include_habituation=cfg.include_habituation,
        include_experimental=not cfg.exclude_experimental,
        max_trials=cfg.max_trials,
        random_seed=cfg.random_seed,
        balance_columns=cfg.balance_columns,
        enrich_from_treatment_labels=cfg.enrich_from_treatment_labels,
    )
