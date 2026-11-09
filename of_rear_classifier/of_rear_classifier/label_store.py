"""Per-scorer rearing labels (syllable-aligned + manual frame intervals).

Collaborators each write their own CSV so multi-rater opinions do not clobber
each other. Sturman-style export merges both sources.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from of_rear_classifier.syllable_bouts import load_bout_table

LABEL_CLASSES = ("Supported", "Unsupported", "Grooming", "None")

LABEL_COLUMNS = (
    "scorer",
    "source",  # syllable | manual
    "bout_index",  # int or empty for manual
    "syllable_id",  # int or empty / -1 for manual
    "t0_frame",
    "t1_frame",
    "label",
)


def sanitize_scorer(name: str) -> str:
    s = re.sub(r"[^\w.\-]+", "_", str(name).strip()) or "scorer"
    return s[:64]


def default_labels_path(bouts_path: Path | str, scorer: str) -> Path:
    """``…/model/labels/<scorer>.csv`` next to ``syllable_bouts.csv``."""
    bouts_path = Path(bouts_path)
    return bouts_path.parent / "labels" / f"{sanitize_scorer(scorer)}.csv"


def _empty_labels() -> pd.DataFrame:
    return pd.DataFrame(columns=list(LABEL_COLUMNS))


def _normalize_labels(df: pd.DataFrame, *, scorer: str) -> pd.DataFrame:
    if df is None or df.empty:
        out = _empty_labels()
        return out
    out = df.copy()
    for col in LABEL_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    out = out.loc[:, list(LABEL_COLUMNS)]
    out["scorer"] = out["scorer"].fillna(scorer).astype(str)
    out["source"] = out["source"].fillna("syllable").astype(str)
    out["label"] = out["label"].astype("string").fillna("").astype(str)
    out["t0_frame"] = pd.to_numeric(out["t0_frame"], errors="coerce").astype("Int64")
    out["t1_frame"] = pd.to_numeric(out["t1_frame"], errors="coerce").astype("Int64")
    out["bout_index"] = pd.to_numeric(out["bout_index"], errors="coerce").astype("Int64")
    out["syllable_id"] = pd.to_numeric(out["syllable_id"], errors="coerce").astype("Int64")
    out = out.dropna(subset=["t0_frame", "t1_frame", "label"])
    out = out[out["label"].astype(str).str.len() > 0]
    out = out.reset_index(drop=True)
    return out


def load_labels(path: Path | str | None, *, scorer: str) -> pd.DataFrame:
    if path is None or not Path(path).is_file():
        return _empty_labels()
    return _normalize_labels(pd.read_csv(path), scorer=scorer)


def save_labels(df: pd.DataFrame, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if not out.empty:
        out["n_frames"] = out["t1_frame"].astype(int) - out["t0_frame"].astype(int) + 1
    out.to_csv(path, index=False)
    return path


def upsert_syllable_label(
    labels: pd.DataFrame,
    *,
    scorer: str,
    bout_index: int,
    syllable_id: int,
    t0_frame: int,
    t1_frame: int,
    label: str,
) -> pd.DataFrame:
    """Replace any existing syllable label for this bout_index + scorer."""
    labels = _normalize_labels(labels, scorer=scorer)
    mask = (labels["source"] == "syllable") & (labels["bout_index"] == bout_index)
    labels = labels.loc[~mask].copy()
    row = {
        "scorer": scorer,
        "source": "syllable",
        "bout_index": int(bout_index),
        "syllable_id": int(syllable_id),
        "t0_frame": int(t0_frame),
        "t1_frame": int(t1_frame),
        "label": str(label),
    }
    return pd.concat([labels, pd.DataFrame([row])], ignore_index=True)


def add_manual_interval(
    labels: pd.DataFrame,
    *,
    scorer: str,
    t0_frame: int,
    t1_frame: int,
    label: str,
) -> pd.DataFrame:
    t0, t1 = int(t0_frame), int(t1_frame)
    if t1 < t0:
        t0, t1 = t1, t0
    labels = _normalize_labels(labels, scorer=scorer)
    row = {
        "scorer": scorer,
        "source": "manual",
        "bout_index": pd.NA,
        "syllable_id": pd.NA,
        "t0_frame": t0,
        "t1_frame": t1,
        "label": str(label),
    }
    return pd.concat([labels, pd.DataFrame([row])], ignore_index=True)


def bout_label_map(labels: pd.DataFrame) -> dict[int, str]:
    """Map bout_index → label for syllable-sourced rows (last write wins)."""
    if labels is None or labels.empty:
        return {}
    sub = labels.loc[labels["source"] == "syllable"].copy()
    if sub.empty:
        return {}
    sub = sub.dropna(subset=["bout_index"])
    out: dict[int, str] = {}
    for _, row in sub.iterrows():
        out[int(row["bout_index"])] = str(row["label"])
    return out


def frame_label_track(
    labels: pd.DataFrame,
    *,
    n_frames: int,
) -> list[str]:
    """Per-frame label string ('' if unlabeled). Later intervals overwrite earlier."""
    track = [""] * int(n_frames)
    if labels is None or labels.empty or n_frames <= 0:
        return track
    for _, row in labels.iterrows():
        t0 = int(row["t0_frame"])
        t1 = int(row["t1_frame"])
        lab = str(row["label"])
        t0 = max(0, t0)
        t1 = min(n_frames - 1, t1)
        for f in range(t0, t1 + 1):
            track[f] = lab
    return track


def labels_to_sturman_intervals(
    labels: pd.DataFrame,
    *,
    fps: float,
    video_id: str,
    scorer: str | None = None,
) -> pd.DataFrame:
    """Labeled intervals → Sturman-like CSV (seconds)."""
    if labels is None or labels.empty:
        return pd.DataFrame(
            columns=["Experimenter", "from", "to", "type", "ID", "source", "bout_index", "syllable_id"]
        )
    lab = labels.copy()
    if scorer is not None:
        lab = lab.loc[lab["scorer"].astype(str) == str(scorer)]
    keep = lab["label"].astype(str).str.len() > 0
    lab = lab.loc[keep]
    return pd.DataFrame(
        {
            "Experimenter": lab["scorer"].astype(str),
            "from": lab["t0_frame"].astype(float) / float(fps),
            "to": (lab["t1_frame"].astype(float) + 1.0) / float(fps),
            "type": lab["label"].astype(str),
            "ID": video_id,
            "source": lab["source"].astype(str),
            "bout_index": lab["bout_index"],
            "syllable_id": lab["syllable_id"],
        }
    )


def migrate_bout_labels_into_store(
    bouts_path: Path | str,
    *,
    scorer: str,
    labels_path: Path | str | None = None,
) -> pd.DataFrame:
    """If ``syllable_bouts.csv`` already has ``label`` cells, import once into the store."""
    bouts = load_bout_table(bouts_path)
    path = Path(labels_path) if labels_path else default_labels_path(bouts_path, scorer)
    labels = load_labels(path if path.is_file() else None, scorer=scorer)
    if not labels.empty:
        return labels
    for _, row in bouts.iterrows():
        lab = str(row.get("label", "") or "").strip()
        if not lab:
            continue
        labels = upsert_syllable_label(
            labels,
            scorer=scorer,
            bout_index=int(row["bout_index"]),
            syllable_id=int(row["syllable_id"]),
            t0_frame=int(row["t0_frame"]),
            t1_frame=int(row["t1_frame"]),
            label=lab,
        )
    return labels
