"""Shared offline processing package for maze acquisition outputs."""

from .process_trial import process_trial
from .run_pipeline import run_pipeline, run_single_trial

__version__ = "0.1.0"

__all__ = [
    "process_trial",
    "run_pipeline",
    "run_single_trial",
]
