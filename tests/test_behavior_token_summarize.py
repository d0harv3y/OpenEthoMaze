"""Tests for behavior-token occupancy and transition summaries."""

from __future__ import annotations

import pytest

from maze.kpms.behavior_ethogram.behavior_token_summarize import (
    aggregate_occupancy_rows,
    bout_in_phase,
    build_transition_rows,
    label_for_grain,
    summarize_bout_rows_from_table,
)
from maze.kpms.behavior_ethogram.behavior_token_labels import validate_ethology_curation_complete
from pathlib import Path

from maze.pipeline.io.file_discovery import TrialManifest


def _bout_row(
    *,
    trial_key: str = "3245_S04_T06",
    bout_index: int,
    behavior_token: int,
    duration_s: float = 1.0,
    primary_state: str = "run",
    seed: str = "fit",
) -> dict[str, str]:
    return {
        "stream": "anatomical",
        "seed": seed,
        "trial_key": trial_key,
        "bout_index": str(bout_index),
        "raw_syllable_id": "1",
        "row_start": str(bout_index * 10),
        "row_end_exclusive": str(bout_index * 10 + 10),
        "bout_frames": "10",
        "bout_duration_s": str(duration_s),
        "bout_mean_speed_mps": "0.1",
        "bout_mean_abs_dheading": "0.1",
        "bout_mean_blob_area_px2": "100",
        "bout_iqr_speed_mps": "0.01",
        "bout_iqr_abs_dheading": "0.01",
        "bout_iqr_blob_area_px2": "10",
        "bout_net_dheading_rad": "0.0",
        "bout_straightness": "0.8",
        "bout_primary_state": primary_state,
        "ambiguous": "0",
        "behavior_token": str(behavior_token),
    }


def _manifest(
    *,
    trial_key: str = "3245_S04_T06",
    session: str = "S04",
    tx: str = "veh",
    sex: str = "M",
    strain: str = "C57",
) -> TrialManifest:
    return TrialManifest(
        animal_id="3245",
        session=session,
        trial="T06",
        input_h5_path=Path("dummy.h5"),
        kpms_recording_key=trial_key,
        sex=sex,
        strain=strain,
        tx=tx,
    )


def test_bout_in_phase_run_and_iti() -> None:
    assert bout_in_phase("run", "run") is True
    assert bout_in_phase("iti", "run") is False
    assert bout_in_phase("iti", "iti") is True
    assert bout_in_phase("run", "iti") is False
    assert bout_in_phase("", "run") is True


def test_summarize_bout_rows_filters_seed() -> None:
    table = [
        _bout_row(bout_index=0, behavior_token=3, seed="fit"),
        _bout_row(bout_index=0, behavior_token=9, seed="042"),
    ]
    rows = summarize_bout_rows_from_table(table, seed="fit")
    assert len(rows) == 1
    assert rows[0].behavior_token == 3


def test_aggregate_occupancy_pooled_and_by_session() -> None:
    table = [
        _bout_row(trial_key="3245_S04_T06", bout_index=0, behavior_token=7, duration_s=2.0),
        _bout_row(trial_key="3245_S04_T06", bout_index=1, behavior_token=7, duration_s=1.0),
        _bout_row(trial_key="3246_S05_T06", bout_index=0, behavior_token=9, duration_s=3.0),
    ]
    bout_rows = summarize_bout_rows_from_table(table, seed="fit")
    manifests = {
        "3245_S04_T06": _manifest(trial_key="3245_S04_T06", session="S04"),
        "3246_S05_T06": _manifest(
            trial_key="3246_S05_T06",
            session="S05",
            tx="veh",
            sex="M",
            strain="C57",
        ),
    }
    token_to_label = {7: "7", 9: "9"}
    pooled = aggregate_occupancy_rows(
        bout_rows,
        manifests_by_trial_key=manifests,
        grain="token",
        phase="run",
        token_to_label=token_to_label,
        by_session=False,
    )
    assert len(pooled) == 2
    by_token = {r["label"]: float(r["occupancy_fraction"]) for r in pooled}
    assert by_token["7"] == pytest.approx(3.0 / 6.0)
    assert by_token["9"] == pytest.approx(3.0 / 6.0)
    assert pooled[0]["session"] == ""

    by_session = aggregate_occupancy_rows(
        bout_rows,
        manifests_by_trial_key=manifests,
        grain="token",
        phase="run",
        token_to_label=token_to_label,
        by_session=True,
    )
    sessions = {r["session"] for r in by_session}
    assert sessions == {"S04", "S05"}


def test_build_transition_rows_counts_pairs() -> None:
    table = [
        _bout_row(trial_key="3245_S04_T06", bout_index=0, behavior_token=7),
        _bout_row(trial_key="3245_S04_T06", bout_index=1, behavior_token=9),
        _bout_row(trial_key="3245_S04_T06", bout_index=2, behavior_token=7),
    ]
    bout_rows = summarize_bout_rows_from_table(table, seed="fit")
    manifests = {"3245_S04_T06": _manifest()}
    rows = build_transition_rows(
        bout_rows,
        manifests_by_trial_key=manifests,
        grain="token",
        phase="run",
        token_to_label={7: "7", 9: "9"},
        by_session=False,
    )
    assert len(rows) == 2
    counts = {(r["label_i"], r["label_j"]): int(r["transition_count"]) for r in rows}
    assert counts[("7", "9")] == 1
    assert counts[("9", "7")] == 1


def test_validate_ethology_curation_complete() -> None:
    labels = [
        {"behavior_token": "7", "token_n_bouts": "25", "behavior_name": "groom", "reviewed_at": "t"},
        {"behavior_token": "9", "token_n_bouts": "5", "behavior_name": "", "reviewed_at": ""},
        {"behavior_token": "10", "token_n_bouts": "30", "behavior_name": "", "reviewed_at": ""},
    ]
    errs = validate_ethology_curation_complete(labels, min_token_bouts=20)
    assert any("10" in e for e in errs)
    assert not any("9" in e for e in errs)


def test_label_for_grain_ethology() -> None:
    assert label_for_grain(7, grain="token", token_to_label={7: "groom"}) == "7"
    assert label_for_grain(7, grain="ethology", token_to_label={7: "groom"}) == "groom"
