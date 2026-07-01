from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random

from ..pipeline.io.file_discovery import (
    TrialManifest,
    apply_treatment_labels,
    discover_trials,
    enrich_manifests_exit_number,
    enrich_manifests_from_treatment_labels,
    enrich_manifests_has_tracking_pose,
    load_manifest_csv,
    load_treatment_labels,
)
from .h5_pose import resolve_canonical_trial_h5


def resolve_cohort_db_path(manifests: list[TrialManifest]) -> Path | None:
    """Return the sole existing ``input_h5_path`` across manifests, if unambiguous."""
    paths: set[Path] = set()
    for m in manifests:
        raw = str(getattr(m, "input_h5_path", "") or "").strip()
        if not raw:
            continue
        p = Path(raw).resolve()
        if p.is_file():
            paths.add(p)
    if len(paths) == 1:
        return next(iter(paths))
    return None


def _manifest_has_usable_pose(manifest: TrialManifest, db_path: Path) -> bool:
    """True when anatomical pose is available in H5 or a local SLEAP sidecar exists."""
    if has_tracking_pose(manifest, db_path):
        return True
    sleap = manifest.sleap_path
    if sleap is not None and Path(sleap).is_file():
        return True
    return False


# TrialManifest fields allowed for stratified balancing (subset sampling only).
BALANCE_COLUMN_CHOICES: frozenset[str] = frozenset(
    {
        "sex",
        "tx",
        "cohort",
        "phase",
        "strain",
        "experiment",
        "drug",
        "researcher",
        "animal_id",
        "session",
        "trial",
        "is_habituation",
        "exit_number",
    }
)


@dataclass(frozen=True)
class SubsetConfig:
    """Settings for trial subset selection."""

    manifest_csv: Path | None = None
    require_sleap: bool = True
    include_habituation: bool = False
    include_experimental: bool = True
    max_trials: int | None = None
    random_seed: int = 42
    # Stratification keys for representative subsampling (must be TrialManifest attrs).
    balance_columns: tuple[str, ...] = ("sex", "tx", "phase", "strain")
    # When loading from CSV, fill blank sex/tx/strain/... from treatment_labels.csv (opt-in).
    enrich_from_treatment_labels: bool = False
    #: Cohort / results HDF5 for ``has_tracking_pose`` when ``input_h5_path`` is empty.
    db_path: Path | None = None


def _effective_db_path(cfg: SubsetConfig) -> Path:
    return Path(cfg.db_path) if cfg.db_path is not None else Path("")


def has_tracking_pose(manifest: TrialManifest, db_path: Path | None = None) -> bool:
    """Return True when the manifest row resolves to ``tracking/anatomical`` in trial H5."""
    if manifest.has_tracking_pose:
        return True
    db = Path(db_path) if db_path is not None else Path("")
    return resolve_canonical_trial_h5(manifest, db) is not None


def load_manifests(cfg: SubsetConfig) -> list[TrialManifest]:
    """Load manifests from CSV or discovery and attach treatment metadata."""
    if cfg.manifest_csv is not None:
        manifests = load_manifest_csv(cfg.manifest_csv)
        if cfg.enrich_from_treatment_labels:
            enrich_manifests_from_treatment_labels(manifests)
    else:
        result = discover_trials()
        manifests = result.trials
        if cfg.enrich_from_treatment_labels:
            labels = load_treatment_labels()
            apply_treatment_labels(result, labels)
    enrich_manifests_exit_number(manifests)
    db_path = _effective_db_path(cfg)
    if not db_path.is_file():
        cohort_db = resolve_cohort_db_path(manifests)
        if cohort_db is not None:
            db_path = cohort_db
    enrich_manifests_has_tracking_pose(
        manifests,
        db_path=db_path if db_path.is_file() else None,
    )
    return manifests


def filter_manifests(manifests: list[TrialManifest], cfg: SubsetConfig) -> list[TrialManifest]:
    """Apply baseline trial filters for kpMS fitting."""
    db_path = _effective_db_path(cfg)
    out: list[TrialManifest] = []
    for m in manifests:
        if cfg.require_sleap and not _manifest_has_usable_pose(m, db_path):
            continue
        if not cfg.include_habituation and m.phase == "habituation":
            continue
        if not cfg.include_experimental and m.phase == "experimental":
            continue
        out.append(m)
    return out


def sample_representative_subset(
    manifests: list[TrialManifest],
    max_trials: int | None,
    random_seed: int,
    balance_columns: tuple[str, ...] = ("sex", "tx", "phase", "strain"),
) -> list[TrialManifest]:
    """
    Select a representative subset by stratifying on ``balance_columns`` only.

    Strategy:
    - Build strata from the Cartesian product of normalized values for those columns
    - Round-robin sample across strata until max_trials is reached
    """
    bad = [c for c in balance_columns if c not in BALANCE_COLUMN_CHOICES]
    if bad:
        raise ValueError(
            f"Unknown balance column(s): {bad}. Allowed: {sorted(BALANCE_COLUMN_CHOICES)}"
        )
    if not balance_columns:
        raise ValueError("balance_columns must be non-empty")

    if max_trials is None or max_trials <= 0 or len(manifests) <= max_trials:
        return sorted(manifests, key=_trial_sort_key)

    strata: dict[tuple[str, ...], list[TrialManifest]] = {}
    for m in manifests:
        k = _stratum_key(m, balance_columns)
        strata.setdefault(k, []).append(m)

    rng = random.Random(random_seed)
    for bucket in strata.values():
        rng.shuffle(bucket)

    stratum_keys = sorted(strata.keys())
    picked: list[TrialManifest] = []
    idx = 0
    while len(picked) < max_trials:
        progressed = False
        for k in stratum_keys:
            bucket = strata[k]
            if idx < len(bucket):
                picked.append(bucket[idx])
                progressed = True
                if len(picked) >= max_trials:
                    break
        if not progressed:
            break
        idx += 1

    return sorted(picked, key=_trial_sort_key)


def _normalize_label(value: str | None) -> str:
    if value is None:
        return "NA"
    txt = str(value).strip()
    if txt == "" or txt.lower() == "nan":
        return "NA"
    return txt


def _stratum_key(m: TrialManifest, columns: tuple[str, ...]) -> tuple[str, ...]:
    parts: list[str] = []
    for col in columns:
        if col == "phase":
            parts.append(_normalize_label(m.phase))
        else:
            parts.append(_normalize_label(getattr(m, col, None)))
    return tuple(parts)


def _trial_sort_key(m: TrialManifest) -> tuple[str, str, str]:
    return (m.animal_id, m.session, m.trial)
