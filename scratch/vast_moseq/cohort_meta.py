"""VAST primary-cohort metadata: sex, strain (wt|tg), tx (RBSF-1|n/a)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from maze.pipeline.io.file_discovery import load_manifest_csv

DEFAULT_MANIFEST = Path(
    r"C:\Users\admin\Documents\work\sack\test2\gerstner_manifest_local_legacy.csv"
)

SEX_ORDER = ("F", "M")
STRAIN_ORDER = ("wt", "tg")
TX_ORDER = ("RBSF-1", "n/a")
SLICE_FACTORS = ("sex", "strain", "tx")


def norm_tx(raw: object) -> str:
    s = str(raw or "").strip()
    if s in ("", "nan", "None", "<NA>"):
        return "n/a"
    return s


def norm_strain(raw: object) -> str:
    s = str(raw or "").strip().lower()
    if s in ("", "nan", "none", "<na>"):
        return ""
    return s


def norm_sex(raw: object) -> str:
    s = str(raw or "").strip().upper()
    return s if s in SEX_ORDER else ""


def load_animal_meta(manifest_path: Path | str = DEFAULT_MANIFEST) -> pd.DataFrame:
    """One row per animal_id with normalized sex, strain, tx."""
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
                "tx": norm_tx(m.tx),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    bad = out[(out["sex"] == "") | (out["strain"] == "") | (out["tx"] == "")]
    if not bad.empty:
        raise ValueError(f"incomplete animal metadata for ids: {bad['animal_id'].tolist()}")
    return out.sort_values("animal_id").reset_index(drop=True)


def attach_animal_meta(df: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """Join authoritative manifest meta; overwrite sex/strain/tx when present."""
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
