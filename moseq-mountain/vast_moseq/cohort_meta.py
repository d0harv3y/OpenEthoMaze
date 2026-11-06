"""VAST primary-cohort metadata: sex, strain (wt|tg), tx (RBSF-1|n/a)."""

from __future__ import annotations

from pathlib import Path

import h5py
import pandas as pd

from maze.pipeline.io.file_discovery import load_manifest_csv

DEFAULT_MANIFEST = Path(
    r"D:\sack\test2\gerstner_manifest_local_legacy.csv"
)

SEX_ORDER = ("F", "M")
STRAIN_ORDER = ("wt", "tg")
TX_ORDER = ("RBSF-1", "n/a")
SLICE_FACTORS = ("sex", "strain", "tx")


def _attr_str(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace").strip()
    if hasattr(raw, "item"):
        try:
            raw = raw.item()
        except Exception:
            pass
    s = str(raw).strip()
    if s.lower() in {"nan", "none", "<na>", "?", ""}:
        return ""
    return s


def norm_tx(raw: object) -> str:
    s = _attr_str(raw)
    if s == "":
        return "n/a"
    key = s.upper().replace("_", "-")
    if key in {"RBSF", "RBSF-1", "RBSF1"}:
        return "RBSF-1"
    if key in {"N/A", "NA", "NONE"}:
        return "n/a"
    return s


def norm_strain(raw: object) -> str:
    s = _attr_str(raw).lower()
    return s if s in STRAIN_ORDER else ""


def norm_sex(raw: object) -> str:
    s = _attr_str(raw).upper()
    return s if s in SEX_ORDER else ""


def _tx_from_manifest_row(m: object) -> str:
    """TrialManifest stores CSV ``tx`` in ``condition`` (no ``.tx`` attribute)."""
    return norm_tx(getattr(m, "tx", None) or getattr(m, "condition", None) or "")


def load_animal_meta(manifest_path: Path | str = DEFAULT_MANIFEST) -> pd.DataFrame:
    """One row per animal_id with normalized sex, strain, tx (from trial manifest CSV)."""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in load_manifest_csv(Path(manifest_path)):
        aid = str(m.animal_id)
        if aid in seen:
            continue
        seen.add(aid)
        rows.append(
            {
                "animal_id": aid,
                "sex": norm_sex(m.sex),
                "strain": norm_strain(m.strain),
                "tx": _tx_from_manifest_row(m),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    bad = out[(out["sex"] == "") | (out["strain"] == "") | (out["tx"] == "")]
    if not bad.empty:
        raise ValueError(f"incomplete animal metadata for ids: {bad['animal_id'].tolist()}")
    return out.sort_values("animal_id").reset_index(drop=True)


def load_animal_meta_from_h5(
    tracking_h5: Path | str,
    *,
    animal_ids: set[str] | None = None,
) -> pd.DataFrame:
    """One row per animal from cohort HDF5 animal-group attrs (sex/strain/tx)."""
    rows: list[dict[str, str]] = []
    with h5py.File(tracking_h5, "r") as f:
        ids = sorted(animal_ids) if animal_ids is not None else sorted(f.keys())
        for aid in ids:
            key = str(aid)
            if key not in f:
                raise KeyError(f"animal_id {key!r} missing from {tracking_h5}")
            attrs = f[key].attrs
            rows.append(
                {
                    "animal_id": key,
                    "sex": norm_sex(attrs.get("sex")),
                    "strain": norm_strain(attrs.get("strain")),
                    "tx": norm_tx(attrs.get("tx")),
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    bad = out[(out["sex"] == "") | (out["strain"] == "") | (out["tx"] == "")]
    if not bad.empty:
        raise ValueError(
            f"incomplete H5 animal metadata for ids: {bad['animal_id'].tolist()}"
        )
    return out.sort_values("animal_id").reset_index(drop=True)


def attach_animal_meta(df: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """Join authoritative animal meta; overwrite sex/strain/tx when present."""
    out = df.copy()
    if "animal_id" not in out.columns:
        raise ValueError("attach_animal_meta requires animal_id")
    m = meta.copy()
    m["animal_id"] = m["animal_id"].astype(str)
    out["animal_id"] = out["animal_id"].astype(str)
    drop_cols = [c for c in ("sex", "strain", "tx") if c in out.columns]
    if drop_cols:
        out = out.drop(columns=drop_cols)
    return out.merge(m, on="animal_id", how="left")
