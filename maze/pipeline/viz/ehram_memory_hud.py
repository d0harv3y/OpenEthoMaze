"""Read WME/RME/RMS for unified overlay HUD from ehram_results-style HDF5."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from maze.core.h5_layout import resolve_ambulation_metrics_group
from maze.pipeline.db._shared import open_db
from maze.pipeline.db.trial_key import TrialKey

_MEMORY_KEYS = (
    "working_memory_errors",
    "reference_memory_errors",
    "reference_memory_successes",
)


def merge_ehram_memory_metrics_into_ram_attrs(
    pipeline_db: Path,
    key: TrialKey,
    ram_attrs: dict[str, Any],
) -> None:
    """Fill *ram_attrs* from ``ambulation metrics/*/summary`` or ``results/table`` when missing."""
    need = any(
        k not in ram_attrs or ram_attrs.get(k) in (None, "", "--")
        for k in _MEMORY_KEYS
    )
    if not need:
        return
    counts = _read_ehram_memory_counts(pipeline_db, key)
    for k in _MEMORY_KEYS:
        if k in counts and (
            k not in ram_attrs or ram_attrs.get(k) in (None, "", "--")
        ):
            ram_attrs[k] = counts[k]


def _read_ehram_memory_counts(
    pipeline_db: Path,
    key: TrialKey,
) -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        with open_db(pipeline_db, "r") as h5:
            p = key.path().lstrip("/")
            g_trial = h5[p]
            g_amb = resolve_ambulation_metrics_group(g_trial)
            if g_amb is not None:
                for pt in ("spot", "spot_hybrid", "centroid", "nose"):
                    if pt not in g_amb:
                        continue
                    gpt = g_amb[pt]
                    if "summary" not in gpt:
                        continue
                    arr = np.asarray(gpt["summary"][:])
                    if arr.size == 0 or arr.dtype.names is None:
                        continue
                    names = set(arr.dtype.names)
                    for k in _MEMORY_KEYS:
                        if k in names:
                            out[k] = int(np.asarray(arr[k]).flat[0])
                    if len(out) == len(_MEMORY_KEYS):
                        return out
            g_res = g_trial.get("results")
            if g_res is not None and "table" in g_res:
                t = np.asarray(g_res["table"][:])
                if t.size == 0 or t.dtype.names is None:
                    return out
                row = t[0]
                for k in _MEMORY_KEYS:
                    if k in t.dtype.names:
                        out[k] = int(row[k])
    except (KeyError, OSError, ValueError, TypeError):
        pass
    return out
