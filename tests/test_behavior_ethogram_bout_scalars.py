"""Unit tests for behavior ethogram bout scalars."""

from __future__ import annotations

import numpy as np
import pytest

from maze.kpms.behavior_ethogram.bout_scalars import (
    DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
    aggregate_bout_scalars,
    bout_ambiguous,
    bout_iqr,
    bout_net_dheading_rad,
    bout_straightness,
    compile_trial_bout_features,
    feature_matrix_for_clustering,
    mean_abs_dheading,
    syllable_runs,
)


def test_syllable_runs_rle() -> None:
    z = np.array([1, 1, 2, 2, 2, 1], dtype=np.int64)
    assert syllable_runs(z) == [(1, 0, 2), (2, 2, 5), (1, 5, 6)]


def test_bout_iqr_orders_coherent_before_bimodal() -> None:
    coherent = [0.10, 0.11, 0.10, 0.12]
    bimodal = [0.02, 0.03, 0.25, 0.28]
    assert bout_iqr(coherent) < bout_iqr(bimodal)


def test_mean_abs_dheading_on_unwrapped_heading() -> None:
    heading = np.array([0.0, 0.2, 0.5, 0.9, 1.1, 1.0, 0.8])
    assert mean_abs_dheading(heading) == pytest.approx(np.mean(np.abs(np.diff(np.unwrap(heading)))))


def test_bout_ambiguous_threshold() -> None:
    borderline = bout_iqr([0.10, 0.10, 0.10, 0.22])
    assert bout_ambiguous(borderline) == (borderline > DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS)


def test_compile_trial_bout_features_one_row_per_syllable_run() -> None:
    z = np.array([3, 3, 3, 7, 7], dtype=np.int64)
    speed = np.array([0.1, 0.12, 0.11, 0.2, 0.22], dtype=np.float64)
    dheading = np.zeros(5)
    area = np.ones(5) * 100.0
    rows = compile_trial_bout_features(
        z,
        speed_mps=speed,
        abs_dheading=dheading,
        blob_area_px2=area,
        heading_rad=np.zeros(5),
        fps=30.0,
    )
    assert len(rows) == 2
    assert rows[0].raw_syllable_id == 3
    assert rows[0].bout_frames == 3
    assert rows[1].raw_syllable_id == 7


def test_feature_matrix_for_clustering_shape() -> None:
    z = np.array([1, 1, 2, 2], dtype=np.int64)
    rows = compile_trial_bout_features(
        z,
        speed_mps=np.array([0.1, 0.1, 0.2, 0.2]),
        abs_dheading=np.zeros(4),
        blob_area_px2=np.ones(4),
        heading_rad=np.zeros(4),
        fps=30.0,
    )
    mat, names = feature_matrix_for_clustering(rows)
    assert mat.shape == (2, 9)
    assert "bout_duration_s" in names


def test_aggregate_bout_scalars_primary_state_majority() -> None:
    feat = aggregate_bout_scalars(
        syllable_id=1,
        bout_index=0,
        row_start=0,
        row_end_exclusive=4,
        speed_mps=[0.1, 0.1, 0.1, 0.1],
        abs_dheading=[0.0, 0.0, 0.0, 0.0],
        blob_area_px2=[1.0, 1.0, 1.0, 1.0],
        heading_rad=None,
        fps=30.0,
        trial_states=["run", "iti", "iti", "iti"],
    )
    assert feat.bout_primary_state == "iti"


def test_bout_straightness_straight_line_is_one() -> None:
    xy = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    assert bout_straightness(xy) == pytest.approx(1.0)


def test_bout_straightness_back_and_forth_is_low() -> None:
    xy = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 0.0], [1.0, 0.0]])
    assert bout_straightness(xy) < 0.4


def test_bout_net_dheading_signed_turn() -> None:
    heading = np.array([0.0, 0.5, 1.0, 1.5])
    assert bout_net_dheading_rad(heading) == pytest.approx(1.5)


def test_compile_trial_includes_net_dheading_and_straightness() -> None:
    z = np.array([3, 3, 3, 3], dtype=np.int64)
    centroid = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]], dtype=np.float64)
    heading = np.array([0.0, 0.2, 0.4, 0.6])
    rows = compile_trial_bout_features(
        z,
        speed_mps=np.ones(4) * 0.1,
        abs_dheading=np.zeros(4),
        blob_area_px2=np.ones(4) * 100.0,
        heading_rad=heading,
        centroid_xy_px=centroid,
        fps=30.0,
    )
    assert len(rows) == 1
    assert rows[0].bout_straightness == pytest.approx(1.0)
    assert rows[0].bout_net_dheading_rad == pytest.approx(0.6)
