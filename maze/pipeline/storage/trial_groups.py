from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

import h5py

from maze.core.trial_settings import parse_timestamp
from maze.core.storage import ensure_trial_group as core_ensure_trial_group

from ._shared import open_db, safe_str
from .trial_key import TrialKey

if TYPE_CHECKING:
    from datetime import datetime


def ensure_trial_group(
    db_path: Optional[Path],
    key: TrialKey,
    video_path: Optional[str] = None,
    sleap_path: Optional[str] = None,
    input_h5_path: Optional[str] = None,
    sleap_model_path: Optional[str] = None,
) -> None:
    """Ensure the trial group exists and set base path attrs."""
    with open_db(db_path, "a") as h5:
        core_ensure_trial_group(
            h5,
            key.animal_id,
            key.session,
            key.trial,
            video_path=safe_str(video_path) if video_path is not None else None,
            sleap_path=safe_str(sleap_path) if sleap_path is not None else None,
            attrs={
                "input_h5_path": (
                    safe_str(input_h5_path) if input_h5_path is not None else None
                ),
                "sleap_model_path": (
                    safe_str(sleap_model_path) if sleap_model_path is not None else None
                ),
            },
        )


def read_trial_meta_for_manifest(
    db_path: Optional[Path], key: TrialKey
) -> tuple[Optional["datetime"], Optional[int]]:
    """Read timestamp and ``n_frames`` from trial attrs for manifest backfill."""
    try:
        with open_db(db_path, "r") as h5:
            g_trial = h5[key.path()]
            attrs = g_trial.attrs
            ts_str = attrs.get("timestamp", None)
            if isinstance(ts_str, bytes):
                ts_str = ts_str.decode("utf-8")
            timestamp = parse_timestamp(ts_str) if ts_str else None
            n_frames = int(attrs["n_frames"]) if "n_frames" in attrs else None
        return (timestamp, n_frames)
    except (KeyError, ValueError, TypeError):
        return (None, None)


def trial_has_settings(db_path: Optional[Path], key: TrialKey) -> bool:
    """Return True when a trial group exists and has core settings attrs."""
    try:
        with open_db(db_path, "r") as h5:
            if key.animal_id not in h5:
                return False
            g_animal = h5[key.animal_id]
            if key.session not in g_animal:
                return False
            g_session = g_animal[key.session]
            if key.trial not in g_session:
                return False
            g_trial = g_session[key.trial]
            return "arena_radius_px" in g_trial.attrs or "trial_start_frame" in g_trial.attrs
    except (KeyError, ValueError):
        return False


def delete_trial_group(db_path: Optional[Path], key: TrialKey) -> None:
    """Delete one trial group from the database."""
    with open_db(db_path, "a") as h5:
        if key.animal_id not in h5:
            return
        g_animal = h5[key.animal_id]
        if key.session not in g_animal:
            return
        g_session = g_animal[key.session]
        if key.trial in g_session:
            del g_session[key.trial]


def delete_animal_group(db_path: Optional[Path], animal_id: str) -> None:
    """Delete a top-level animal group after pruning its trials."""
    with open_db(db_path, "a") as h5:
        if animal_id in h5 and animal_id != "metadata":
            del h5[animal_id]


def list_trials(db_path: Optional[Path] = None) -> list[TrialKey]:
    """List all trials in the database."""
    trials = []
    with open_db(db_path, "r") as h5:
        for animal_id in h5.keys():
            if animal_id == "metadata":
                continue
            g_animal = h5[animal_id]
            if not isinstance(g_animal, h5py.Group):
                continue
            for session in g_animal.keys():
                g_session = g_animal[session]
                if not isinstance(g_session, h5py.Group):
                    continue
                for trial in g_session.keys():
                    g_trial = g_session[trial]
                    if isinstance(g_trial, h5py.Group):
                        trials.append(
                            TrialKey(animal_id=animal_id, session=session, trial=trial)
                        )
    return sorted(trials, key=lambda t: (t.animal_id, t.session, t.trial))
