from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import h5py
import numpy as np
from maze.core.h5_layout import write_group_attrs

from ._shared import ensure_group, open_db, safe_str

if TYPE_CHECKING:
    from ..io.file_discovery import TrialManifest


def upsert_trial_manifest_row(db_path: Optional[Path], manifest: "TrialManifest") -> None:
    """Append or replace one row in ``metadata/trial_manifest``."""
    from ..io.file_discovery import MANIFEST_CSV_FIELDNAMES, trial_manifest_csv_row_values

    vals = trial_manifest_csv_row_values(manifest)
    row_key = (str(manifest.animal_id), str(manifest.session), str(manifest.trial))
    dt = np.dtype(
        [(name, h5py.string_dtype(encoding="utf-8")) for name in MANIFEST_CSV_FIELDNAMES]
    )

    def decode_cell(x: Any) -> str:
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="replace")
        if x is None:
            return ""
        return str(x)

    with open_db(db_path, "a") as h5:
        meta = ensure_group(h5, "metadata")
        name = "trial_manifest"
        rows: list[tuple[str, ...]] = []
        if name in meta:
            old = meta[name][:]
            for i in range(old.shape[0]):
                rows.append(tuple(decode_cell(old[i][fn]) for fn in MANIFEST_CSV_FIELDNAMES))
            replaced = False
            for i, row in enumerate(rows):
                if (row[0], row[1], row[3]) == row_key:
                    rows[i] = tuple(str(v) for v in vals)
                    replaced = True
                    break
            if not replaced:
                rows.append(tuple(str(v) for v in vals))
        else:
            rows.append(tuple(str(v) for v in vals))
        new_arr = np.array(rows, dtype=dt)
        if name in meta:
            del meta[name]
        meta.create_dataset(
            name,
            data=new_arr,
            compression="gzip",
            chunks=(min(64, max(1, len(new_arr))),),
        )


def write_trial_manifest_rows(
    db_path: Optional[Path],
    manifests: list["TrialManifest"],
) -> None:
    """Rewrite ``metadata/trial_manifest`` once from a list of manifests."""
    from ..io.file_discovery import MANIFEST_CSV_FIELDNAMES, trial_manifest_csv_row_values

    dt = np.dtype(
        [(name, h5py.string_dtype(encoding="utf-8")) for name in MANIFEST_CSV_FIELDNAMES]
    )
    rows = [tuple(str(v) for v in trial_manifest_csv_row_values(m)) for m in manifests]
    arr = np.array(rows, dtype=dt)
    with open_db(db_path, "a") as h5:
        meta = ensure_group(h5, "metadata")
        name = "trial_manifest"
        if name in meta:
            del meta[name]
        meta.create_dataset(
            name,
            data=arr,
            compression="gzip",
            chunks=(min(256, max(1, len(arr))),),
        )


def write_animal_label(
    db_path: Optional[Path],
    animal_id: str,
    sex: Optional[str] = None,
    tx: Optional[str] = None,
    strain: Optional[str] = None,
    experiment: Optional[str] = None,
    researcher: Optional[str] = None,
    drug: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """Write treatment labels for an animal."""
    with open_db(db_path, "a") as h5:
        g_animal = h5[animal_id] if animal_id in h5 else h5.create_group(animal_id)
        write_group_attrs(
            g_animal,
            {
                "sex": safe_str(sex) if sex is not None else None,
                "tx": safe_str(tx) if tx is not None else None,
                "strain": safe_str(strain) if strain is not None else None,
                "experiment": safe_str(experiment) if experiment is not None else None,
                "researcher": safe_str(researcher) if researcher is not None else None,
                "drug": safe_str(drug) if drug is not None else None,
                "notes": safe_str(notes) if notes is not None else None,
            },
        )


def read_animal_label(
    db_path: Optional[Path],
    animal_id: str,
) -> dict[str, str]:
    """Read treatment labels for an animal."""
    try:
        with open_db(db_path, "r") as h5:
            if animal_id not in h5:
                return {}
            g_animal = h5[animal_id]
            return {
                "sex": safe_str(g_animal.attrs.get("sex", "")),
                "tx": safe_str(g_animal.attrs.get("tx", "")),
                "notes": safe_str(g_animal.attrs.get("notes", "")),
                "strain": safe_str(g_animal.attrs.get("strain", "")),
                "experiment": safe_str(g_animal.attrs.get("experiment", "")),
                "researcher": safe_str(g_animal.attrs.get("researcher", "")),
                "drug": safe_str(g_animal.attrs.get("drug", "")),
            }
    except (KeyError, ValueError):
        return {}
