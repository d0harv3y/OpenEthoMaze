"""CSV I/O for bout feature tables.

Column order: ``bout_feature_contract.BOUT_TABLE_FIELDS``;
see ``docs/bout_feature_contract.md``.
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from .bout_feature_contract import BOUT_TABLE_FIELDS
from .bout_scalars import BoutScalarFeatures


def bout_row_to_dict(
    feat: BoutScalarFeatures,
    *,
    stream: str,
    seed: str,
    trial_key: str,
    cluster_id: int | None = None,
    behavior_token: int | None = None,
) -> dict[str, Any]:
    d = asdict(feat)
    d.update(
        {
            "stream": stream,
            "seed": seed,
            "trial_key": trial_key,
            "cluster_id": "" if cluster_id is None else int(cluster_id),
            "behavior_token": "" if behavior_token is None else int(behavior_token),
            "ambiguous": int(bool(feat.ambiguous)),
            "bout_mean_heading_rad": "" if feat.bout_mean_heading_rad is None else feat.bout_mean_heading_rad,
            "bout_iqr_heading_rad": "" if feat.bout_iqr_heading_rad is None else feat.bout_iqr_heading_rad,
        }
    )
    return d


def write_bout_table_csv(path: Path | str, rows: Sequence[dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(BOUT_TABLE_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_bout_table_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _parse_float(raw: str, default: float = 0.0) -> float:
    text = str(raw).strip()
    if not text:
        return default
    return float(text)


def _parse_optional_float(raw: str) -> float | None:
    text = str(raw).strip()
    if not text:
        return None
    return float(text)


def dict_to_bout_scalar_features(row: Mapping[str, str]) -> BoutScalarFeatures:
    return BoutScalarFeatures(
        raw_syllable_id=int(row["raw_syllable_id"]),
        bout_index=int(row["bout_index"]),
        row_start=int(row["row_start"]),
        row_end_exclusive=int(row["row_end_exclusive"]),
        bout_frames=int(row["bout_frames"]),
        bout_duration_s=_parse_float(row["bout_duration_s"]),
        bout_mean_speed_mps=_parse_float(row["bout_mean_speed_mps"]),
        bout_mean_abs_dheading=_parse_float(row["bout_mean_abs_dheading"]),
        bout_mean_blob_area_px2=_parse_float(row["bout_mean_blob_area_px2"]),
        bout_iqr_speed_mps=_parse_float(row["bout_iqr_speed_mps"]),
        bout_iqr_abs_dheading=_parse_float(row["bout_iqr_abs_dheading"]),
        bout_iqr_blob_area_px2=_parse_float(row["bout_iqr_blob_area_px2"]),
        bout_mean_heading_rad=_parse_optional_float(row.get("bout_mean_heading_rad", "")),
        bout_iqr_heading_rad=_parse_optional_float(row.get("bout_iqr_heading_rad", "")),
        bout_net_dheading_rad=_parse_float(row.get("bout_net_dheading_rad", "0")),
        bout_straightness=_parse_float(row.get("bout_straightness", "0")),
        bout_primary_state=str(row.get("bout_primary_state", "")),
        ambiguous=bool(int(row.get("ambiguous", "0"))),
    )
