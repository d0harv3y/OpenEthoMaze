"""S1 anchor: is_moving deep module + calibration (pure, no I/O)."""

from __future__ import annotations

import numpy as np
import pytest

from maze.kpms.behavior_ethogram.anchor import (
    IsMovingParams,
    calibrate_is_moving_params,
    calibrate_min_dwell_ms,
    is_moving,
    speed_histogram_antimode,
    speed_mps_from_xy_px,
)


def test_is_moving_requires_enter_above_exit() -> None:
    with pytest.raises(ValueError, match="enter_mps"):
        is_moving(
            np.array([0.1, 0.2]),
            fps=30.0,
            enter_mps=0.05,
            exit_mps=0.1,
            min_dwell_ms=50.0,
        )


def test_is_moving_enters_after_min_dwell_above_enter_threshold() -> None:
    fps = 10.0
    # 100 ms @ 10 fps => 1 frame debounce
    speed = np.array([0.0, 0.0, 0.5, 0.5, 0.5, 0.0, 0.0], dtype=np.float64)
    out = is_moving(
        speed,
        fps=fps,
        enter_mps=0.3,
        exit_mps=0.1,
        min_dwell_ms=100.0,
    )
    assert out.dtype == bool
    assert not out[0]
    assert not out[1]
    assert out[2]
    assert out[3]
    assert out[4]
    assert not out[5]


def test_is_moving_hysteresis_holds_between_enter_and_exit() -> None:
    fps = 10.0
    speed = np.array([0.5, 0.5, 0.5, 0.2, 0.2, 0.2, 0.05, 0.05, 0.05, 0.05], dtype=np.float64)
    out = is_moving(
        speed,
        fps=fps,
        enter_mps=0.3,
        exit_mps=0.1,
        min_dwell_ms=100.0,
    )
    # Enter at 0; hold through 0.2 band until sustained below exit.
    assert out[0]
    assert out[3]
    assert not out[-1]


def test_is_moving_invalid_frames_force_still_and_reset() -> None:
    fps = 10.0
    speed = np.array([0.5, 0.5, 0.5, 0.5, 0.5], dtype=np.float64)
    valid = np.array([True, True, False, True, False])
    out = is_moving(
        speed,
        fps=fps,
        enter_mps=0.3,
        exit_mps=0.1,
        min_dwell_ms=200.0,  # 2 frames — one valid frame after gap cannot re-enter
        valid=valid,
    )
    assert out[0]
    assert out[1]
    assert not out[2]
    assert not out[3]
    assert not out[4]


def test_speed_mps_from_xy_px_matches_step_speed() -> None:
    xy = np.array([[0.0, 0.0], [100.0, 0.0]], dtype=np.float64)
    speed = speed_mps_from_xy_px(xy, fps=10.0, px_per_cm=1.0)
    assert speed[0] == 0.0
    assert speed[1] == pytest.approx(10.0)  # 1 m displacement @ 10 fps


def test_speed_histogram_antimode_splits_still_and_moving_peaks() -> None:
    rng = np.random.default_rng(0)
    still = rng.normal(0.02, 0.005, size=500)
    move = rng.normal(0.25, 0.05, size=500)
    speed = np.concatenate([still, move])
    enter, exit_ = speed_histogram_antimode(speed)
    assert enter > exit_
    assert 0.05 < enter < 0.5
    assert exit_ < 0.1


def test_calibrate_min_dwell_ms_prefers_less_fragmentation() -> None:
    fps = 20.0
    speed = np.zeros(40, dtype=np.float64)
    speed[5:8] = 0.4
    speed[20:23] = 0.4
    params = IsMovingParams(enter_mps=0.3, exit_mps=0.1, min_dwell_ms=50.0)
    dwell = calibrate_min_dwell_ms(
        speed,
        params,
        fps=fps,
        candidates_ms=(50.0, 150.0, 300.0),
    )
    assert dwell in (50.0, 150.0, 300.0)


def test_calibrate_is_moving_params_returns_usable_thresholds() -> None:
    rng = np.random.default_rng(1)
    speed = np.concatenate([rng.normal(0.02, 0.005, 200), rng.normal(0.3, 0.05, 200)])
    params = calibrate_is_moving_params(
        speed,
        fps=30.0,
        dwell_candidates_ms=(50.0, 100.0, 200.0),
    )
    assert params.enter_mps > params.exit_mps
    assert params.min_dwell_ms in (50.0, 100.0, 200.0)
    mask = is_moving(
        speed,
        fps=30.0,
        enter_mps=params.enter_mps,
        exit_mps=params.exit_mps,
        min_dwell_ms=params.min_dwell_ms,
    )
    assert mask.any()
    assert (~mask).any()
