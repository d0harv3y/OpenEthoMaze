"""Push file discovery + treatment labels into a target results H5 (GUI / batch)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence

from .db import (
    TrialKey,
    ensure_trial_group,
    init_database,
    write_animal_label,
    write_trial_manifest_rows,
)
from .io.file_discovery import DiscoveryResult
from .sources.legacy_vast import (
    apply_treatment_labels,
    check_duplicates,
    discover_trials,
    load_treatment_labels,
    update_treatment_labels_from_discovery,
)


def sync_discovery_into_h5(
    db_path: Path,
    *,
    treatment_labels_path: Optional[Path] = None,
    merge_new_label_ids: bool = False,
    data_dirs: Optional[Sequence[Path]] = None,
) -> tuple[DiscoveryResult, list[Any]]:
    """
    Run discovery, apply labels, ensure trial groups, write animal attrs + manifest rows.

    ``data_dirs`` overrides :data:`maze.pipeline.paths.DATA_DIRS` when non-empty.

    Returns ``(discovery_result, duplicates)`` from :func:`check_duplicates`.
    """
    db_path = Path(db_path)
    init_database(db_path)
    dirs_arg: Path | list[Path] | None
    if data_dirs:
        dirs_arg = [Path(d) for d in data_dirs]
    else:
        dirs_arg = None
    result = discover_trials(dirs_arg)
    tpath = Path(treatment_labels_path) if treatment_labels_path else None
    if merge_new_label_ids and tpath is not None:
        update_treatment_labels_from_discovery(result, tpath)
    labels = load_treatment_labels(tpath)
    apply_treatment_labels(result, labels)
    duplicates = check_duplicates(result)

    for trial in result.trials:
        key = TrialKey.from_manifest(trial)
        ih5: Optional[str] = None
        if trial.input_h5_path:
            p = Path(trial.input_h5_path)
            if p.exists():
                ih5 = str(p)
        ensure_trial_group(
            db_path,
            key,
            video_path=str(trial.video_path) if trial.video_path else None,
            sleap_path=str(trial.sleap_path) if trial.sleap_path else None,
            input_h5_path=ih5,
        )

    unique_animals: set[str] = set()
    for trial in result.trials:
        aid = trial.effective_animal_id
        if aid in unique_animals:
            continue
        unique_animals.add(aid)
        lab = labels.get(aid)
        notes = (lab.notes if lab else None) or None
        write_animal_label(
            db_path,
            aid,
            strain=trial.strain,
            experiment=trial.experiment,
            sex=trial.sex,
            tx=trial.tx,
            researcher=trial.researcher,
            drug=trial.drug,
            notes=notes,
        )

    write_trial_manifest_rows(db_path, result.trials)
    return result, duplicates
