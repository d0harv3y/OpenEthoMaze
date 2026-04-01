"""Tracking data processing module."""

from .trace_processing import (
    process_xy_trace,
    process_trace_data,
    filter_frames_no_animal,
    TraceProcessingParams,
)

__all__ = [
    "process_xy_trace",
    "process_trace_data",
    "filter_frames_no_animal",
    "TraceProcessingParams",
]
