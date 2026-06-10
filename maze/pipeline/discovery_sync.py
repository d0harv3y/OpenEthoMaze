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
from .run_provenance import provenance_run, sha256_file
from .treatment_labels_csv import validate_treatment_labels_csv
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
    prov_inputs = {
        "db_path": str(db_path),
        "treatment_labels_path": str(treatment_labels_path) if treatment_labels_path else None,
        "merge_new_label_ids": merge_new_label_ids,
        "data_dirs": [str(Path(d)) for d in data_dirs] if data_dirs else None,
    }
    with provenance_run("discovery_sync", db_path, prov_inputs) as prov:
        init_database(db_path)
        dirs_arg: Path | list[Path] | None
        if data_dirs:
            dirs_arg = [Path(d) for d in data_dirs]
        else:
            dirs_arg = None
        result = discover_trials(
            dirs_arg,
            exclude_h5_paths=[db_path],
            controller_results_h5=db_path,
        )
        tpath = Path(treatment_labels_path) if treatment_labels_path else None
        if tpath is not None:
            validate_treatment_labels_csv(tpath)
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
                has_tracking_pose=trial.has_tracking_pose,
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
        prov["outputs"] = {
            "n_trials": len(result.trials),
            "n_duplicates": len(duplicates),
            "n_input_h5_files": len(result.input_h5_files),
        }
        if tpath is not None and tpath.is_file():
            prov["outputs"]["treatment_labels_sha256"] = sha256_file(tpath)
        return result, duplicates
