"""Trial key normalization and HDF5 paths (Phase A A6)."""

from __future__ import annotations

from maze.pipeline.db.trial_key import TrialKey, canonical_ram_trial


def test_canonical_ram_trial_normalizes_numeric_and_prefixed() -> None:
    assert canonical_ram_trial("1") == "T01"
    assert canonical_ram_trial("T1") == "T01"
    assert canonical_ram_trial("t09") == "T09"
    assert canonical_ram_trial("custom") == "custom"


def test_trial_key_path_is_hdf5_group_path() -> None:
    key = TrialKey(animal_id="556", session="S01", trial="T02")
    assert key.path() == "/556/S01/T02"
    assert key.phase == "experimental"


def test_trial_key_habituation_phase() -> None:
    key = TrialKey(animal_id="556", session="hS01", trial="T01")
    assert key.phase == "habituation"
