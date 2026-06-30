"""Contract sync tests: bout CSV columns and ML feature name lists."""

from __future__ import annotations

import numpy as np

from maze.kpms.behavior_ethogram import bout_feature_contract as contract
from maze.kpms.behavior_ethogram.arhmm import build_trial_sequences_from_table
from maze.kpms.behavior_ethogram.bout_scalars import (
    compile_trial_bout_features,
    feature_matrix_for_clustering,
)
from maze.kpms.behavior_ethogram.bout_table_io import BOUT_TABLE_FIELDS
from maze.kpms.behavior_ethogram.syllable_signature import SYLLABLE_SIGNATURE_NAMES


def test_contract_internal_sync() -> None:
    contract.assert_contract_in_sync()


def test_doc_pins_schema_version() -> None:
    from pathlib import Path

    doc = Path(__file__).resolve().parents[1] / "docs" / "bout_feature_contract.md"
    content = doc.read_text(encoding="utf-8")
    assert contract.BOUT_FEATURE_SCHEMA_VERSION in content
    assert "bout_feature_contract.py" in content


def test_bout_table_fields_reexport_matches_contract() -> None:
    assert BOUT_TABLE_FIELDS == contract.BOUT_TABLE_FIELDS


def test_clustering_feature_names_match_matrix() -> None:
    rows = _sample_rows()
    _, names = feature_matrix_for_clustering(rows)
    assert names == list(contract.CLUSTERING_FEATURE_NAMES)


def test_optional_heading_feature_names_match_matrix() -> None:
    z = np.array([1, 1, 2, 2], dtype=np.int64)
    rows = compile_trial_bout_features(
        z,
        speed_mps=np.array([0.1, 0.1, 0.2, 0.2]),
        abs_dheading=np.zeros(4),
        blob_area_px2=np.ones(4),
        heading_rad=np.array([0.0, 0.5, 1.0, 1.5]),
        fps=30.0,
        include_heading_direction=True,
    )
    _, names = feature_matrix_for_clustering(rows, include_heading_direction=True)
    assert names == [
        *contract.CLUSTERING_FEATURE_NAMES,
        *contract.OPTIONAL_HEADING_FEATURE_NAMES,
    ]


def test_syllable_signature_names_match_contract() -> None:
    assert SYLLABLE_SIGNATURE_NAMES == contract.SYLLABLE_SIGNATURE_FEATURE_NAMES


def test_arhmm_default_feature_names_match_build_sequences() -> None:
    table = [_table_row(sid=1, speed=0.1), _table_row(sid=2, speed=0.2, bout_index=1, row_start=2, row_end=4)]
    seqs = build_trial_sequences_from_table(table)
    assert seqs[0].features.shape[1] == len(contract.arhmm_feature_names())


def _sample_rows():
    z = np.array([3, 3, 7, 7], dtype=np.int64)
    return compile_trial_bout_features(
        z,
        speed_mps=np.array([0.1, 0.1, 0.2, 0.2]),
        abs_dheading=np.zeros(4),
        blob_area_px2=np.ones(4),
        heading_rad=np.zeros(4),
        fps=30.0,
    )


def _table_row(
    *,
    sid: int,
    speed: float,
    bout_index: int = 0,
    row_start: int = 0,
    row_end: int = 2,
) -> dict[str, str]:
    return {
        "seed": "042",
        "trial_key": "1-S01-T01",
        "raw_syllable_id": str(sid),
        "bout_index": str(bout_index),
        "row_start": str(row_start),
        "row_end_exclusive": str(row_end),
        "bout_frames": str(row_end - row_start),
        "bout_duration_s": "0.1",
        "bout_mean_speed_mps": str(speed),
        "bout_mean_abs_dheading": "0.05",
        "bout_mean_blob_area_px2": "100",
        "bout_iqr_speed_mps": "0.01",
        "bout_iqr_abs_dheading": "0.01",
        "bout_iqr_blob_area_px2": "1",
        "bout_net_dheading_rad": "0",
        "bout_straightness": "1",
    }

