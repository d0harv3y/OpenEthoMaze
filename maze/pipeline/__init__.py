"""Shared offline processing package for maze acquisition outputs.

Import entry points from their modules (avoids circular imports at package init):

- ``from maze.pipeline.process_trial import process_trial``
- ``from maze.pipeline.run_pipeline import run_pipeline, run_single_trial``
"""

from __future__ import annotations

__version__ = "0.1.0"
