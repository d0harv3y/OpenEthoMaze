"""Artifact paths under ``behavior_ethogram/`` (cohort artifact root)."""

from __future__ import annotations

from pathlib import Path


def behavior_ethogram_root(kpms_root: Path | str) -> Path:
    return Path(kpms_root) / "behavior_ethogram"


def stage_ii_dir(kpms_root: Path | str) -> Path:
    return behavior_ethogram_root(kpms_root) / "stage_ii"


def stage_iii_dir(kpms_root: Path | str, *, seed: str | None = None) -> Path:
    base = behavior_ethogram_root(kpms_root) / "stage_iii"
    if seed is None:
        return base
    return base / f"seed_{seed}"


def bout_features_csv(stage_ii: Path | str) -> Path:
    return Path(stage_ii) / "bout_features.csv"


def bout_features_clustered_csv(stage_ii: Path | str) -> Path:
    return Path(stage_ii) / "bout_features_clustered.csv"


def hdbscan_summary_json(stage_ii: Path | str) -> Path:
    return Path(stage_ii) / "hdbscan_summary.json"


def arhmm_checkpoint_h5(stage_iii: Path | str) -> Path:
    return Path(stage_iii) / "bout_arhmm_checkpoint.h5"


def arhmm_fit_summary_json(stage_iii: Path | str) -> Path:
    return Path(stage_iii) / "bout_arhmm_fit_summary.json"


def bout_tokens_csv(stage_iii: Path | str) -> Path:
    return Path(stage_iii) / "bout_behavior_tokens.csv"


def locomotion_rules_yaml(stage_iii: Path | str) -> Path:
    return Path(stage_iii) / "locomotion_tiers.yaml"


def token_tiers_csv(stage_iii: Path | str) -> Path:
    return Path(stage_iii) / "token_tiers.csv"


def discover_anatomical_seeds(kpms_root: Path | str) -> tuple[str, ...]:
    """Return sorted seed ids with ``anatomical/seed_*/results_apply.h5``."""
    root = Path(kpms_root) / "anatomical"
    if not root.is_dir():
        return ()
    seeds: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or not child.name.startswith("seed_"):
            continue
        if (child / "results_apply.h5").is_file():
            seeds.append(child.name.removeprefix("seed_"))
    return tuple(seeds)
