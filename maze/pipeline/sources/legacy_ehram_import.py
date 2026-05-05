"""Import legacy RAM ``SourceWorkItem`` rows into the shared ORM HDF5 database.

This is the pipeline-owned seam for batch legacy ingestion; CLI wrappers can call
these functions without importing old ``ehram`` code.

Typical flow:

1. :func:`discover_legacy_ehram_work_items` (``trial_ns.csv`` + paired ``.mp4`` / ``.h5.slp``)
2. :func:`bootstrap_legacy_ram_database` on a **dedicated** output path
3. :func:`import_legacy_ram_work_items`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from maze.core.h5_layout import init_task_database
from maze.core.tasks import ARENA_TYPE_RADIAL_ARM

from ...controller.acquisition.h5_writer import compute_radial_arm_settings_payloads
from ...controller.acquisition.radial_arm.config import RadialArmControllerConfig
from ...controller.acquisition.radial_arm.legacy_template import apply_legacy_template_config
from ..db import (
    ensure_trial_group,
    init_database,
    trial_has_settings,
    write_animal_label,
    write_radial_arm_trial_settings,
)
from ..db.trial_key import TrialKey
from ..work_items import SourceWorkItem
from .legacy_ehram import discover_legacy_ehram_work_items


@dataclass
class LegacyRamImportResult:
    """Summary of one :func:`import_legacy_ram_work_items` run."""

    n_imported: int = 0
    n_skipped: int = 0
    n_errors: int = 0
    errors: list[str] = field(default_factory=list)


def legacy_ram_work_item_to_trial_key(item: SourceWorkItem) -> TrialKey:
    """Map a normalized legacy RAM work item to a :class:`TrialKey`."""
    return TrialKey(
        animal_id=item.animal_id,
        session=item.session_key,
        trial=item.trial_key,
    )


def bootstrap_legacy_ram_database(db_path: Path | str) -> None:
    """
    Ensure ``db_path`` exists with pipeline metadata and ``radial_arm`` arena type.

    Use a **dedicated** HDF5 path for RAM legacy imports; do not mix with circular
    VAST legacy databases.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    if new_file:
        init_task_database(
            path,
            arena_type=ARENA_TYPE_RADIAL_ARM,
            arena_description="Radial-arm maze (legacy import)",
        )
    init_database(path)


def _escape_arm_index(item: SourceWorkItem) -> int:
    raw = item.metadata.get("escape_arm", "0")
    try:
        v = int(str(raw).strip())
    except (TypeError, ValueError):
        return 0
    # Legacy trial_ns values are 1-based; normalize to internal 0-based.
    if 1 <= v <= 8:
        return v - 1
    return v


def import_legacy_ram_work_items(
    db_path: Path | str,
    work_items: Sequence[SourceWorkItem],
    *,
    skip_existing_with_settings: bool = True,
) -> LegacyRamImportResult:
    """
    Write trial groups, shared RAM settings, and geometry for each work item.

    Geometry uses the ORM-migrated legacy template (:func:`apply_legacy_template_config`).
    """
    out = LegacyRamImportResult()
    path = Path(db_path)
    if not path.exists():
        bootstrap_legacy_ram_database(path)

    seen_animals: set[str] = set()

    for item in work_items:
        if item.arena_type != ARENA_TYPE_RADIAL_ARM:
            out.n_errors += 1
            out.errors.append(f"skip non-RAM item: {item.work_key}")
            continue
        key = legacy_ram_work_item_to_trial_key(item)
        try:
            if skip_existing_with_settings and trial_has_settings(path, key):
                out.n_skipped += 1
                continue

            ensure_trial_group(
                path,
                key,
                video_path=str(item.video_path) if item.video_path else None,
                sleap_path=str(item.sleap_path) if item.sleap_path else None,
                input_h5_path=None,
            )

            escape_idx = _escape_arm_index(item)
            escape_idx = max(0, min(7, escape_idx))

            cfg = RadialArmControllerConfig()
            apply_legacy_template_config(cfg)
            cfg.radial_arm.exit_arm_index = escape_idx

            ts = (
                item.timestamp.isoformat()
                if item.timestamp is not None
                else None
            )
            phase = str(item.phase or "legacy_ram").strip() or "legacy_ram"

            trial_attrs, task_attrs, geometry_payload = (
                compute_radial_arm_settings_payloads(
                    cfg,
                    timestamp=ts,
                    phase=phase,
                    run_mode="continuous",
                    trial_start_frame=0,
                )
            )
            write_radial_arm_trial_settings(
                path,
                key,
                trial_attrs=trial_attrs,
                task_attrs=task_attrs,
                geometry_payload=geometry_payload,
            )

            if item.animal_id and item.animal_id not in seen_animals:
                seen_animals.add(item.animal_id)
                sex = (item.metadata.get("sex") or "").strip() or None
                tx = (item.metadata.get("tx") or "").strip() or None
                write_animal_label(path, item.animal_id, sex=sex, tx=tx)

            out.n_imported += 1
        except Exception as e:
            out.n_errors += 1
            out.errors.append(f"{key.path()}: {e}")

    return out


def discover_and_import_legacy_ram(
    base_dir: Path | str,
    *,
    trial_ns_path: Path | str,
    db_path: Path | str,
    skip_existing_with_settings: bool = True,
) -> LegacyRamImportResult:
    """
    Discover work items under ``base_dir`` and import them into ``db_path``.

    Convenience wrapper around :func:`discover_legacy_ehram_work_items` and
    :func:`import_legacy_ram_work_items`.
    """
    bootstrap_legacy_ram_database(db_path)
    items = discover_legacy_ehram_work_items(
        base_dir, trial_ns_path=trial_ns_path
    )
    return import_legacy_ram_work_items(
        db_path,
        items,
        skip_existing_with_settings=skip_existing_with_settings,
    )


__all__ = [
    "LegacyRamImportResult",
    "bootstrap_legacy_ram_database",
    "discover_and_import_legacy_ram",
    "discover_legacy_ehram_work_items",
    "import_legacy_ram_work_items",
    "legacy_ram_work_item_to_trial_key",
]
