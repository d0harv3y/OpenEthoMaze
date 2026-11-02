"""Operator settings + storage helpers (grill 2026-10-22)."""

from __future__ import annotations

from pathlib import Path

from app.operator_state import (
    CHUNK_DEFAULT_LITE_MIN,
    CHUNK_DEFAULT_STANDARD_MIN,
    DEFAULT_RECORDING_TAG,
    chunk_preset_minutes,
    estimate_gb_per_hour,
    is_session_dirname,
    load_operator_state,
    normalize_recording_tag,
    patch_cam_meta,
    save_operator_state,
    session_folder,
    storage_health,
)


def test_session_folder_uses_recording_tag(tmp_path: Path) -> None:
    p = session_folder(tmp_path, "", "20261022T180000Z")
    assert p == tmp_path / "ses-20261022T180000Z"
    p2 = session_folder(tmp_path, "runs", "20261022T180000Z")
    assert p2 == tmp_path / "runs" / "ses-20261022T180000Z"
    p3 = session_folder(
        tmp_path, "", "20261022T180000Z", recording_tag="pretest"
    )
    assert p3 == tmp_path / "pretest-20261022T180000Z"
    assert is_session_dirname("ses-20261022T180000Z")
    assert is_session_dirname("pretest-20261022T180000Z")
    assert not is_session_dirname("runs")


def test_chunk_presets() -> None:
    assert chunk_preset_minutes("lite") == CHUNK_DEFAULT_LITE_MIN
    assert chunk_preset_minutes("standard") == CHUNK_DEFAULT_STANDARD_MIN


def test_normalize_recording_tag() -> None:
    assert normalize_recording_tag("") == DEFAULT_RECORDING_TAG
    assert normalize_recording_tag("  pretest  ") == "pretest"
    assert normalize_recording_tag("a/b c") == "a-b-c"
    assert len(normalize_recording_tag("x" * 100)) == 64


def test_h5_pack_and_recording_tag_defaults(tmp_path: Path) -> None:
    st = load_operator_state(tmp_path)
    assert st["h5_pack"] is True
    assert st["recording_tag"] == DEFAULT_RECORDING_TAG
    saved = save_operator_state(
        tmp_path,
        {
            **st,
            "h5_pack": False,
            "recording_tag": "day1 run",
        },
    )
    assert saved["h5_pack"] is False
    assert saved["recording_tag"] == "day1-run"
    again = load_operator_state(tmp_path)
    assert again["h5_pack"] is False
    assert again["recording_tag"] == "day1-run"
    # Empty tag falls back to default — one shape always.
    cleared = save_operator_state(tmp_path, {**again, "recording_tag": ""})
    assert cleared["recording_tag"] == DEFAULT_RECORDING_TAG


def test_save_load_and_freeze_subject(tmp_path: Path) -> None:
    st = save_operator_state(
        tmp_path,
        {
            "profile": "lite",
            "soft_fps": 10,
            "output_subdir": "lab",
            "chunk_minutes": 0,
            "cameras": {"bhvr-cam0": {"subject_id": "m1", "sex": "F"}},
        },
    )
    assert st["chunk_minutes"] == 0
    assert st["profile"] == "lite"
    assert st["h5_pack"] is True
    loaded = load_operator_state(tmp_path)
    assert loaded["cameras"]["bhvr-cam0"]["subject_id"] == "m1"
    patch_cam_meta(
        tmp_path,
        "bhvr-cam0",
        {"subject_id": "hacked", "cage_id": "c9"},
        freeze_subject=True,
    )
    again = load_operator_state(tmp_path)["cameras"]["bhvr-cam0"]
    assert again["subject_id"] == "m1"
    assert again["cage_id"] == "c9"


def test_estimate_and_storage(tmp_path: Path) -> None:
    est = estimate_gb_per_hour("standard", 30, 4)
    assert est["n_cams"] == 4
    assert est["gb_per_hour"] > 0
    h = storage_health(tmp_path)
    assert h["mounted"] is True
    assert h["free_gb"] is not None
