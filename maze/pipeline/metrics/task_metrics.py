from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ...core.tasks import ARENA_TYPE_RADIAL_ARM
from .exit_metrics import (
    CenterMetrics,
    ExitMetrics,
    calculate_center_metrics,
    calculate_exit_metrics,
)


@dataclass(frozen=True)
class TaskMetricsResult:
    """Task-specific metrics plus any extra trial attrs to persist."""

    exit_metrics: ExitMetrics
    center_metrics: CenterMetrics
    extra_trial_attrs: dict[str, Any] = field(default_factory=dict)


def radial_arm_metric_defaults() -> dict[str, Any]:
    """Return the first RAM metric contract persisted before full analytics land."""
    return {
        "task_metrics_status": "radial_arm_contract_ready",
        "working_memory_errors": np.nan,
        "reference_memory_errors": np.nan,
        "reference_memory_successes": np.nan,
        "exit_arm": -1,
    }


def calculate_task_metrics(
    *,
    arena_type: str,
    xy: np.ndarray,
    valid: np.ndarray,
    exit_pos: tuple[float, float],
    arena_center_pos: tuple[float, float],
    px_per_cm: float,
    fps: float,
    exit_zone_radius_cm: float,
    center_zone_radius_cm: float,
) -> TaskMetricsResult:
    """Dispatch task-specific metric calculations for a trajectory band."""
    if arena_type == ARENA_TYPE_RADIAL_ARM:
        return TaskMetricsResult(
            exit_metrics=ExitMetrics(),
            center_metrics=CenterMetrics(),
            extra_trial_attrs=radial_arm_metric_defaults(),
        )

    return TaskMetricsResult(
        exit_metrics=calculate_exit_metrics(
            xy=xy,
            valid=valid,
            exit_pos=exit_pos,
            px_per_cm=px_per_cm,
            fps=fps,
            exit_zone_radius_cm=exit_zone_radius_cm,
        ),
        center_metrics=calculate_center_metrics(
            xy=xy,
            valid=valid,
            arena_center_pos=arena_center_pos,
            px_per_cm=px_per_cm,
            fps=fps,
            center_zone_radius_cm=center_zone_radius_cm,
        ),
        extra_trial_attrs={"task_metrics_status": "ok", "arena_type": arena_type},
    )


def summary_fields_for_task(
    *,
    arena_type: str,
    exit_metrics: ExitMetrics,
    center_metrics: CenterMetrics,
) -> dict[str, float | int]:
    """Map task-specific metrics to the shared summary dtype."""
    if arena_type == ARENA_TYPE_RADIAL_ARM:
        return {
            "latency_to_exit_s": np.nan,
            "time_in_exit_zone_s": 0.0,
            "time_in_exit_zone_fraction": 0.0,
            "mean_distance_to_exit_cm": np.nan,
            "min_distance_to_exit_cm": np.nan,
            "path_efficiency": np.nan,
            "n_exit_zone_entries": 0,
            "time_in_center_s": 0.0,
            "time_in_center_fraction": 0.0,
            "n_center_entries": 0,
        }

    return {
        "latency_to_exit_s": exit_metrics.latency_to_exit_s,
        "time_in_exit_zone_s": exit_metrics.time_in_exit_zone_s,
        "time_in_exit_zone_fraction": exit_metrics.time_in_exit_zone_fraction,
        "mean_distance_to_exit_cm": exit_metrics.mean_distance_to_exit_cm,
        "min_distance_to_exit_cm": exit_metrics.min_distance_to_exit_cm,
        "path_efficiency": exit_metrics.path_efficiency,
        "n_exit_zone_entries": exit_metrics.n_exit_zone_entries,
        "time_in_center_s": center_metrics.time_in_center_s,
        "time_in_center_fraction": center_metrics.time_in_center_fraction,
        "n_center_entries": center_metrics.n_center_entries,
    }
