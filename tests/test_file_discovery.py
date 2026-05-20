"""file_discovery parsing and manifest CSV contract (Phase A A6)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from maze.pipeline.io.file_discovery import (
    MANIFEST_CSV_FIELDNAMES,
    parse_sleap_filename,
    parse_video_filename,
    trial_manifest_csv_row_values,
)

from conftest import make_manifest


def test_parse_video_filename_extracts_ids() -> None:
    assert parse_video_filename(Path("556_S2T09.avi")) == ("556", "S02", "T09")
    assert parse_video_filename(Path("not_a_trial.mp4")) is None


def test_parse_sleap_filename_extracts_ids() -> None:
    assert parse_sleap_filename(Path("556_S2T09.h5.slp")) == ("556", "S02", "T09")
    assert parse_sleap_filename(Path("556_S2T09.analysis.h5")) == ("556", "S02", "T09")
    assert parse_sleap_filename(Path("bad.slp")) is None


def test_trial_manifest_csv_row_values_matches_fieldnames() -> None:
    ts = datetime(2024, 6, 1, 12, 0, 0)
    m = make_manifest(
        animal_id="556",
        session="S02",
        trial="T03",
        input_h5_path=Path("data/in.h5"),
        video_path=Path("data/v.avi"),
        sleap_path=Path("data/p.h5.slp"),
        h5_n_frames=100,
        video_n_frames=99,
        timestamp=ts,
        sex="M",
        tx="SF",
        cohort="vast",
        kpms_recording_key="556-S02-T03",
    )
    row = trial_manifest_csv_row_values(m)
    assert len(row) == len(MANIFEST_CSV_FIELDNAMES)
    assert MANIFEST_CSV_FIELDNAMES[0] == "animal_id"
    assert row[0] == "556"
    assert row[1] == "S02"
    assert row[3] == "T03"
    assert row[13] == ts.isoformat()
    assert row[14] == "100"
    assert row[15] == "99"
    assert row[16] == "-1"
    assert row[17].endswith("in.h5")
    assert row[20] == "556-S02-T03"
