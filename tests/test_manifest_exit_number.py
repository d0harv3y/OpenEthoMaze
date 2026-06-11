"""Manifest exit_number column and kpMS balance stratification."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from maze.core.trial_settings import TrialSettings
from maze.kpms.manifest_subset import BALANCE_COLUMN_CHOICES, sample_representative_subset
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import (
    DiscoveryResult,
    MANIFEST_CSV_FIELDNAMES,
    enrich_manifests_exit_number,
    load_manifest_csv,
    save_manifest_csv,
    trial_manifest_csv_row_values,
)

from conftest import make_manifest


def test_exit_number_in_manifest_csv_round_trip(tmp_path: Path) -> None:
    manifest = make_manifest(exit_number=3)
    csv_path = tmp_path / "manifest.csv"
    save_manifest_csv(DiscoveryResult(trials=[manifest]), csv_path)

    assert "exit_number" in MANIFEST_CSV_FIELDNAMES
    row = trial_manifest_csv_row_values(manifest)
    exit_idx = MANIFEST_CSV_FIELDNAMES.index("exit_number")
    assert row[exit_idx] == "3"

    loaded = load_manifest_csv(csv_path)[0]
    assert loaded.exit_number == 3


def test_balance_by_exit_number_stratifies() -> None:
    assert "exit_number" in BALANCE_COLUMN_CHOICES
    trials = [
        make_manifest(animal_id="1", session="S01", trial="T01", exit_number=1),
        make_manifest(animal_id="2", session="S01", trial="T01", exit_number=2),
        make_manifest(animal_id="3", session="S01", trial="T01", exit_number=1),
        make_manifest(animal_id="4", session="S01", trial="T01", exit_number=2),
    ]
    picked = sample_representative_subset(
        trials,
        max_trials=2,
        random_seed=0,
        balance_columns=("exit_number",),
    )
    exits = {m.exit_number for m in picked}
    assert len(picked) == 2
    assert exits == {1, 2}


def test_enrich_manifests_exit_number_from_results_h5_attr(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("7", "S01", "T02")
    with h5py.File(db, "w") as h5:
        g = h5.create_group(key.path().lstrip("/"))
        g.attrs["exit_number"] = 4

    manifest = make_manifest(
        animal_id="7",
        session="S01",
        trial="T02",
        input_h5_path=db,
        exit_number=None,
    )
    enrich_manifests_exit_number([manifest])
    assert manifest.exit_number == 4


def test_enrich_manifests_exit_number_from_legacy_settings(monkeypatch, tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.h5"
    legacy.touch()
    manifest = make_manifest(input_h5_path=legacy, exit_number=None)

    def _fake_settings(*_args, **_kwargs) -> TrialSettings:
        return TrialSettings(
            arena_center_x_px=0.0,
            arena_center_y_px=0.0,
            arena_radius_px=100.0,
            px_per_cm=2.42,
            stage="VAST",
            color="",
            timestamp=None,
            exit_number=2,
        )

    monkeypatch.setattr(
        "maze.pipeline.io.input_h5_loader.load_trial_settings",
        _fake_settings,
    )
    enrich_manifests_exit_number([manifest])
    assert manifest.exit_number == 2
