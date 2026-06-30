"""Tests for syllable kinematic signature embedding (S2)."""

from __future__ import annotations

import numpy as np

from maze.kpms.behavior_ethogram.bout_scalars import BoutScalarFeatures, feature_matrix_for_arhmm
from maze.kpms.behavior_ethogram.syllable_signature import (
    SYLLABLE_SIGNATURE_NAMES,
    build_syllable_kinematic_signatures,
    max_scalar_correlation_with_signature,
    syllable_signature_row,
)


def _feat(*, sid: int, speed: float) -> BoutScalarFeatures:
    return BoutScalarFeatures(
        raw_syllable_id=sid,
        bout_index=0,
        row_start=0,
        row_end_exclusive=3,
        bout_frames=3,
        bout_duration_s=0.1,
        bout_mean_speed_mps=speed,
        bout_mean_abs_dheading=0.1,
        bout_mean_blob_area_px2=100.0,
        bout_iqr_speed_mps=0.01,
        bout_iqr_abs_dheading=0.01,
        bout_iqr_blob_area_px2=1.0,
        bout_net_dheading_rad=0.0,
        bout_straightness=1.0,
    )


def test_syllable_signature_pools_by_raw_syllable_id() -> None:
    rows = [_feat(sid=1, speed=0.1), _feat(sid=1, speed=0.3), _feat(sid=2, speed=0.5)]
    sigs = build_syllable_kinematic_signatures(rows)
    assert sigs[1][0] == 0.2
    assert sigs[2][0] == 0.5


def test_feature_matrix_appends_signature_not_cluster_id() -> None:
    rows = [_feat(sid=1, speed=0.2), _feat(sid=2, speed=0.4)]
    sigs = build_syllable_kinematic_signatures(rows)
    append = np.stack([syllable_signature_row(r, sigs) for r in rows])
    mat, names = feature_matrix_for_arhmm(rows, append_columns=append, append_names=SYLLABLE_SIGNATURE_NAMES)
    assert mat.shape == (2, 9 + len(SYLLABLE_SIGNATURE_NAMES))
    assert "cluster_id" not in names
    assert names[-1] == "syllable_sig_mean_blob_area_px2"


def test_signature_adds_independent_signal_vs_bout_speed() -> None:
    rows = [_feat(sid=i % 3, speed=0.05 * i) for i in range(30)]
    sigs = build_syllable_kinematic_signatures(rows)
    append = np.stack([syllable_signature_row(r, sigs) for r in rows])
    mat, names = feature_matrix_for_arhmm(rows, append_columns=append, append_names=SYLLABLE_SIGNATURE_NAMES)
    max_r = max_scalar_correlation_with_signature(mat, names)
    assert max_r < 0.99
