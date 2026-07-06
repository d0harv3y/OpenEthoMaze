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


def producers_root(kpms_root: Path | str) -> Path:
    """Root for producer-agnostic Behavior labeling artifacts (S0 contract)."""
    return behavior_ethogram_root(kpms_root) / "producers"


def producer_dir(kpms_root: Path | str, producer: str, fit_id: str) -> Path:
    """One Behavior labeling artifact dir: ``producers/<producer>/<fit_id>/``."""
    return producers_root(kpms_root) / str(producer) / str(fit_id)


def behavior_frames_h5(artifact_dir: Path | str) -> Path:
    return Path(artifact_dir) / "behavior_frames.h5"


def behavior_bouts_csv(artifact_dir: Path | str) -> Path:
    return Path(artifact_dir) / "behavior_bouts.csv"


def behavior_provenance_json(artifact_dir: Path | str) -> Path:
    return Path(artifact_dir) / "provenance.json"


def anchors_root(kpms_root: Path | str) -> Path:
    return behavior_ethogram_root(kpms_root) / "anchors"


def anchor_dir(kpms_root: Path | str, anchor_name: str, calibration_id: str) -> Path:
    return anchors_root(kpms_root) / str(anchor_name) / str(calibration_id)


def anchor_frames_h5(artifact_dir: Path | str) -> Path:
    return Path(artifact_dir) / "anchor_frames.h5"


def anchor_provenance_json(artifact_dir: Path | str) -> Path:
    return Path(artifact_dir) / "provenance.json"


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


def resolve_results_h5_path(
    kpms_root: Path | str,
    seed: str,
    *,
    results_h5: Path | None = None,
) -> Path:
    """Resolve kpMS syllable results H5 for compile (apply seed dir or cohort fit)."""
    if results_h5 is not None:
        return Path(results_h5)
    root = Path(kpms_root)
    apply_path = root / "anatomical" / f"seed_{seed}" / "results_apply.h5"
    if apply_path.is_file():
        return apply_path
    fit_path = root / "results.h5"
    if fit_path.is_file():
        return fit_path
    return apply_path


def discover_compile_seeds(
    kpms_root: Path | str,
    *,
    results_h5: Path | None = None,
) -> tuple[str, ...]:
    """Seed ids for compile: apply seeds on disk, or ``fit`` when only ``results.h5`` exists."""
    if results_h5 is not None:
        return ("fit",)
    apply_seeds = discover_anatomical_seeds(kpms_root)
    if apply_seeds:
        return apply_seeds
    if (Path(kpms_root) / "results.h5").is_file():
        return ("fit",)
    return ()


def locomotion_rules_yaml(stage_iii: Path | str) -> Path:
    return Path(stage_iii) / "locomotion_tiers.yaml"


def token_tiers_csv(stage_iii: Path | str) -> Path:
    return Path(stage_iii) / "token_tiers.csv"


def token_grid_movies_dir(stage_iii: Path | str) -> Path:
    return Path(stage_iii) / "grid_movies"


def behavior_token_labels_csv(stage_iii: Path | str) -> Path:
    return Path(stage_iii) / "behavior_token_labels.csv"


def grammar_dir(kpms_root: Path | str, *, seed: str) -> Path:
    """Per-seed Option A workspace: mined candidates + curated rules."""
    return behavior_ethogram_root(kpms_root) / "grammar" / f"seed_{seed}"


def grammar_candidates_csv(grammar: Path | str) -> Path:
    return Path(grammar) / "candidate_sequences.csv"


def grammar_candidate_exemplars_json(grammar: Path | str) -> Path:
    return Path(grammar) / "candidate_exemplars.json"


def grammar_rules_json(grammar: Path | str) -> Path:
    return Path(grammar) / "grammar_rules.json"


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
