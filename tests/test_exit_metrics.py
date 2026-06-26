"""Tests for exit-related band metrics."""

from __future__ import annotations

import math

import numpy as np

from maze.pipeline.metrics.exit_metrics import calculate_exit_metrics


def test_last_frame_distance_uses_last_valid_frame_not_last_array_index() -> None:
    px_per_cm = 10.0
    exit_pos = (100.0, 0.0)
    xy = np.array(
        [
            [100.0, 0.0],  # 0 cm
            [110.0, 0.0],  # 1 cm
            [120.0, 0.0],  # 2 cm — last valid
            [999.0, 0.0],  # invalid trailing frame
        ],
        dtype=float,
    )
    valid = np.array([True, True, True, False])

    metrics = calculate_exit_metrics(
        xy=xy,
        valid=valid,
        exit_pos=exit_pos,
        px_per_cm=px_per_cm,
        fps=30.0,
    )

    assert metrics.last_frame_distance_to_exit_cm == 2.0
    assert metrics.min_distance_to_exit_cm == 0.0


def test_last_frame_distance_nan_when_no_valid_frames() -> None:
    xy = np.array([[0.0, 0.0], [10.0, 0.0]], dtype=float)
    valid = np.array([False, False])

    metrics = calculate_exit_metrics(
        xy=xy,
        valid=valid,
        exit_pos=(0.0, 0.0),
        px_per_cm=10.0,
        fps=30.0,
    )

    assert math.isnan(metrics.last_frame_distance_to_exit_cm)


def test_last_frame_distance_single_valid_frame() -> None:
    xy = np.array([[50.0, 0.0], [60.0, 0.0]], dtype=float)
    valid = np.array([False, True])

    metrics = calculate_exit_metrics(
        xy=xy,
        valid=valid,
        exit_pos=(0.0, 0.0),
        px_per_cm=10.0,
        fps=30.0,
    )

    assert metrics.last_frame_distance_to_exit_cm == 6.0
