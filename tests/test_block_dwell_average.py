from __future__ import annotations

from pathlib import Path

import numpy as np

from maze.cli.average_block_dwell_plots import _load_manifest_rows
from maze.pipeline.viz.block_dwell_average import (
    IMAGE_SIZE,
    accumulate_run_dwell_grid_cm,
    average_block_dwell,
    export_filename,
    export_filename_pooled,
    export_relpath,
    export_relpath_pooled,
    TrialRunSample,
)


def test_accumulate_run_dwell_grid_cm_places_mass_at_center() -> None:
    xy_px = np.array([[100.0, 100.0]], dtype=np.float64)
    valid = np.array([True])
    grid = accumulate_run_dwell_grid_cm(
        xy_px,
        valid,
        arena_center_x_px=100.0,
        arena_center_y_px=100.0,
        px_per_cm=10.0,
        fps=10.0,
        blur_sigma=0.0,
    )
    center = IMAGE_SIZE // 2
    assert grid[center, center] > 0.0
    assert np.isclose(float(grid.sum()), 0.1)


def test_average_block_dwell_per_animal_first() -> None:
    g1 = np.ones((IMAGE_SIZE, IMAGE_SIZE), dtype=np.float32)
    g2 = np.zeros((IMAGE_SIZE, IMAGE_SIZE), dtype=np.float32)
    g3 = np.full((IMAGE_SIZE, IMAGE_SIZE), 3.0, dtype=np.float32)
    samples = [
        TrialRunSample(1, "S01", "T01", g1, 0.0, 0.0, 12.5),
        TrialRunSample(1, "S01", "T02", g2, 1.0, 0.0, 12.5),
        TrialRunSample(2, "S01", "T01", g3, 0.0, 1.0, 12.5),
    ]
    grid, exits, n_units, n_unique_animals, n_trials = average_block_dwell(samples)
    assert n_units == 2
    assert n_unique_animals == 2
    assert n_trials == 3
    assert len(exits) == 3
    assert grid.shape == (IMAGE_SIZE, IMAGE_SIZE)
    # animal 1 mean = 0.5, animal 2 = 3.0 -> overall 1.75
    assert np.isclose(float(grid[0, 0]), 1.75)


def test_export_paths() -> None:
    assert export_filename("S01", "RBSF", "wt", "F", "1-3") == "S01_RBSF_wt_F_trial1-3.png"
    assert export_relpath("S02", "RBSF-1", "tg", "M", "4-6") == Path("S02/RBSF-1/S02_RBSF-1_tg_M_trial4-6.png")
    assert export_relpath("S01", "n/a", "wt", "F", "1-3") == Path("S01/n_a/S01_n_a_wt_F_trial1-3.png")
    assert export_filename("S02", "RBSF", "wt", "M", "1-9") == "S02_RBSF_wt_M_trial1-9.png"
    assert export_filename_pooled("RBSF", "wt", "F", "1-3") == "ALL_RBSF_wt_F_trial1-3.png"
    assert export_relpath_pooled("n/a", "tg", "M", "7-9") == Path("n_a/ALL_n_a_tg_M_trial7-9.png")


def test_average_block_dwell_keeps_sessions_separate_for_same_animal() -> None:
    g1 = np.ones((IMAGE_SIZE, IMAGE_SIZE), dtype=np.float32)
    g2 = np.full((IMAGE_SIZE, IMAGE_SIZE), 3.0, dtype=np.float32)
    samples = [
        TrialRunSample(1, "S01", "T01", g1, 0.0, 0.0, 12.5),
        TrialRunSample(1, "S02", "T01", g2, 0.0, 0.0, 12.5),
    ]
    grid, _, n_units, n_unique_animals, n_trials = average_block_dwell(samples)
    assert n_units == 2
    assert n_unique_animals == 1
    assert n_trials == 2
    assert np.isclose(float(grid[0, 0]), 2.0)


def test_load_manifest_rows_keeps_literal_na_treatment(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "animal_id,session,trial,phase,sex,strain,tx,researcher\n"
        "1,S01,T01,experimental,F,wt,n/a,Emma|Hayden\n"
        "2,S01,T01,experimental,M,tg,RBSF,Emma|Hayden\n",
        encoding="utf-8",
    )
    rows = _load_manifest_rows(
        manifest,
        phase="experimental",
        researcher="Emma|Hayden",
        sessions=("S01",),
    )
    assert set(rows.tx.tolist()) == {"n/a", "RBSF"}
