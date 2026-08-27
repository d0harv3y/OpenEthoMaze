"""Toy litmus for NOR syllable bout kinematics helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.bout_kinematics import (  # noqa: E402
    KINEMATICS_FIELDS,
    immobile_spans_from_movement,
    model_num_states,
    spans_from_movement_recs,
    spot_speed_mps,
    spot_step_length_m,
)


def test_model_num_states() -> None:
    assert model_num_states("paramscan_s1-1e8_s2-1e5_ss-50") == 50
    assert model_num_states("paramscan_ss-10_extra") == 10
    assert not np.isfinite(model_num_states("nope"))


def test_spot_speed_constant_motion() -> None:
    # 1 m/s along x at 10 fps → 0.1 m/frame
    fps = 10.0
    t = np.arange(5, dtype=np.float64)
    x = 0.1 * t
    y = np.zeros_like(x)
    valid = np.ones(5, dtype=bool)
    speed = spot_speed_mps(x, y, valid, fps)
    assert np.isnan(speed[0])
    np.testing.assert_allclose(speed[1:], 1.0, rtol=1e-9)


def test_spot_speed_invalid_endpoint() -> None:
    x = np.array([0.0, 0.1, 0.2], dtype=np.float64)
    y = np.zeros(3)
    valid = np.array([True, False, True])
    speed = spot_speed_mps(x, y, valid, 10.0)
    assert np.isnan(speed[0])
    assert np.isnan(speed[1])
    assert np.isnan(speed[2])


def test_spot_path_length() -> None:
    x = np.array([0.0, 3.0, 3.0, 7.0], dtype=np.float64)
    y = np.array([0.0, 0.0, 4.0, 4.0], dtype=np.float64)
    valid = np.ones(4, dtype=bool)
    step = spot_step_length_m(x, y, valid)
    assert np.isnan(step[0])
    np.testing.assert_allclose(step[1:], [3.0, 4.0, 4.0], rtol=1e-9)
    assert float(np.nansum(step)) == 11.0


def test_movement_spans_end_exclusive() -> None:
    recs = np.array(
        [(13, 161, 148), (270, 270, 0)],
        dtype=[("start_frame", "i4"), ("end_frame", "i4"), ("duration_frames", "i4")],
    )
    spans = spans_from_movement_recs(recs)
    assert spans == [(0, 13, 161)]
    assert spans[0][2] - spans[0][1] == 148


def test_immobile_spans_pre_between_post() -> None:
    move = [(0, 10, 20), (1, 40, 50)]
    gaps = immobile_spans_from_movement(move, 60)
    assert gaps == [(0, 0, 10), (1, 20, 40), (2, 50, 60)]


def test_immobile_spans_no_movement_is_whole_session() -> None:
    assert immobile_spans_from_movement([], 12) == [(0, 0, 12)]


def test_immobile_spans_adjacent_and_overlap() -> None:
    assert immobile_spans_from_movement([(0, 0, 5), (1, 5, 10)], 10) == []
    # overlap / nested merge → one block, gaps on both sides
    gaps = immobile_spans_from_movement([(0, 2, 8), (1, 4, 6)], 10)
    assert gaps == [(0, 0, 2), (1, 8, 10)]


def test_kinematics_fields_include_speed_and_heading() -> None:
    assert "bout_mean_speed_mps" in KINEMATICS_FIELDS
    assert "bout_mean_abs_dheading" in KINEMATICS_FIELDS
    assert "raw_syllable_id" in KINEMATICS_FIELDS


def test_align_truncation_lengths() -> None:
    from nor_object_mi.bout_kinematics import _align_len

    a = np.arange(10)
    b = np.arange(7)
    aa, bb = _align_len(a, b)
    assert aa.shape[0] == 7 and bb.shape[0] == 7
