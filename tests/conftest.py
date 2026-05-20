"""Shared pytest fixtures for OpenEthoMaze."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from maze.pipeline.io.file_discovery import TrialManifest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """OpenEthoMaze repository root (parent of ``maze/``)."""
    return Path(__file__).resolve().parents[1]


def make_manifest(
    *,
    animal_id: str = "42",
    session: str = "S01",
    trial: str = "T01",
    input_h5_path: Path | str = "inputs/trial.h5",
    video_path: Path | str | None = None,
    sleap_path: Path | str | None = None,
    is_habituation: bool = False,
    h5_n_frames: int | None = None,
    video_n_frames: int | None = None,
    **extra: Any,
) -> TrialManifest:
    """Build a :class:`TrialManifest` for unit tests (no binary fixtures in git)."""
    return TrialManifest(
        animal_id=animal_id,
        session=session,
        trial=trial,
        input_h5_path=Path(input_h5_path),
        video_path=Path(video_path) if video_path is not None else None,
        sleap_path=Path(sleap_path) if sleap_path is not None else None,
        is_habituation=is_habituation,
        h5_n_frames=h5_n_frames,
        video_n_frames=video_n_frames,
        timestamp=extra.pop("timestamp", None),
        sex=extra.pop("sex", None),
        strain=extra.pop("strain", None),
        tx=extra.pop("tx", None),
        cohort=extra.pop("cohort", None),
        researcher=extra.pop("researcher", None),
        original_session=extra.pop("original_session", None),
        kpms_recording_key=extra.pop("kpms_recording_key", None),
        **extra,
    )


@pytest.fixture
def manifest_factory():
    """Callable fixture that returns :func:`make_manifest`."""
    return make_manifest
