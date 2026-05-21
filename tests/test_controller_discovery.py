"""Controller-first discovery defaults and filename parsing (Phase C C1)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from maze.pipeline.controller_discovery import (
    default_discovery_data_dirs,
    default_results_h5_path,
    default_treatment_labels_path,
)
from maze.pipeline.io.file_discovery import (
    discover_trials,
    parse_sleap_filename,
    parse_video_filename,
)


def test_parse_controller_mp4_filename() -> None:
    assert parse_video_filename(Path("42_S01_T01.mp4")) == ("42", "S01", "T01")
    assert parse_video_filename(Path("556_S2T09.avi")) == ("556", "S02", "T09")


def test_parse_controller_predictions_slp() -> None:
    assert parse_sleap_filename(Path("42_S01_T01.predictions.slp")) == (
        "42",
        "S01",
        "T01",
    )


def test_default_results_h5_path_uses_output_dir() -> None:
    cfg = SimpleNamespace(output_dir=r"C:\data\cohort1", h5_filename="trials.h5")
    assert default_results_h5_path(cfg) == Path(r"C:\data\cohort1") / "trials.h5"


def test_default_discovery_data_dirs_controller_first() -> None:
    cfg = SimpleNamespace(output_dir=r"C:\data\cohort1", h5_filename="trials.h5")
    assert default_discovery_data_dirs(cfg) == [Path(r"C:\data\cohort1")]
    empty = SimpleNamespace(output_dir=None, h5_filename="trials.h5")
    assert default_discovery_data_dirs(empty) is None


def test_default_treatment_labels_under_output_dir() -> None:
    cfg = SimpleNamespace(output_dir=r"C:\data\cohort1", h5_filename="trials.h5")
    assert default_treatment_labels_path(cfg) == Path(r"C:\data\cohort1") / "treatment_labels.csv"


def test_discover_trials_controller_video_fallback(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    db.touch()
    (tmp_path / "99_S01_T02.mp4").touch()
    (tmp_path / "99_S01_T02.predictions.slp").touch()

    with patch("maze.pipeline.io.file_discovery.discover_input_h5_files", return_value=[]):
        with patch(
            "maze.pipeline.io.file_discovery.discover_video_files",
            return_value=[tmp_path / "99_S01_T02.mp4"],
        ):
            with patch(
                "maze.pipeline.io.file_discovery.discover_sleap_files",
                return_value=[tmp_path / "99_S01_T02.predictions.slp"],
            ):
                result = discover_trials(
                    tmp_path,
                    exclude_h5_paths=[db],
                    controller_results_h5=db,
                )

    assert len(result.trials) == 1
    t = result.trials[0]
    assert t.animal_id == "99"
    assert t.session == "S01"
    assert t.trial == "T02"
    assert t.video_path == tmp_path / "99_S01_T02.mp4"
    assert t.sleap_path == tmp_path / "99_S01_T02.predictions.slp"
    assert t.input_h5_path == db
