"""Behavioral metrics computation module."""

from .ambulation import (
    calculate_ambulation_metrics,
    calculate_distance_traveled,
    AmbulationMetrics,
)
from .exit_metrics import (
    calculate_exit_metrics,
    build_xy_table_with_exit,
    ExitMetrics,
)

__all__ = [
    # Ambulation
    "calculate_ambulation_metrics",
    "calculate_distance_traveled",
    "AmbulationMetrics",
    # Exit metrics
    "calculate_exit_metrics",
    "build_xy_table_with_exit",
    "ExitMetrics",
]
