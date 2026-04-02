"""Legacy VAST source adapter for offline discovery and manifest handling."""

from __future__ import annotations

from pathlib import Path

from ...core.tasks import ARENA_TYPE_CIRCULAR
from ..io.file_discovery import (
    DiscoveryResult,
    TrialManifest,
    apply_treatment_labels,
    check_duplicates,
    discover_trials,
    load_manifest_csv,
    load_treatment_labels,
    save_manifest_csv,
    update_treatment_labels_from_discovery,
)
from ..work_items import SourceWorkItem


def manifest_to_work_item(manifest: TrialManifest) -> SourceWorkItem:
    """Normalize a legacy VAST manifest into the shared source-adapter contract."""
    metadata = {}
    if manifest.original_session:
        metadata["original_session"] = manifest.original_session
    if manifest.inferred_id:
        metadata["inferred_id"] = manifest.inferred_id
    if manifest.sex:
        metadata["sex"] = manifest.sex
    if manifest.tx:
        metadata["tx"] = manifest.tx
    if manifest.strain:
        metadata["strain"] = manifest.strain
    if manifest.experiment:
        metadata["experiment"] = manifest.experiment
    if manifest.drug:
        metadata["drug"] = manifest.drug

    return SourceWorkItem(
        source_name="legacy_vast",
        arena_type=ARENA_TYPE_CIRCULAR,
        animal_id=manifest.animal_id,
        session_key=manifest.session,
        trial_key=manifest.trial,
        phase=manifest.phase,
        input_h5_path=manifest.input_h5_path,
        video_path=manifest.video_path,
        sleap_path=manifest.sleap_path,
        timestamp=manifest.timestamp,
        cohort=manifest.cohort,
        researcher=manifest.researcher,
        raw_name=manifest.trial_key,
        metadata=metadata,
    )


def discover_legacy_vast_work_items(
    data_dirs: list[Path | str] | None = None,
) -> list[SourceWorkItem]:
    """Discover legacy VAST trials and project them into normalized work items."""
    discovery = discover_trials(data_dirs=data_dirs)
    return [manifest_to_work_item(trial) for trial in discovery.trials]


__all__ = [
    "DiscoveryResult",
    "TrialManifest",
    "apply_treatment_labels",
    "check_duplicates",
    "discover_trials",
    "discover_legacy_vast_work_items",
    "load_manifest_csv",
    "load_treatment_labels",
    "manifest_to_work_item",
    "save_manifest_csv",
    "update_treatment_labels_from_discovery",
]
