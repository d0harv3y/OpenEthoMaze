"""HTU21D env JSONL append helper (unit; no MQTT / FastAPI)."""

from __future__ import annotations

import json
from pathlib import Path

from app.env_log import append_env_jsonl


def _active(tmp_path: Path) -> Path:
    folder = tmp_path / "ses-test"
    folder.mkdir()
    active = {
        "folder": str(folder),
        "meta": {
            "camera_ids": ["bhvr-cam0"],
            "subject_id": "m1",
            "cameras": {"bhvr-cam0": {"subject_id": "m1"}},
        },
    }
    active_path = tmp_path / ".active_session.json"
    active_path.write_text(json.dumps(active) + "\n", encoding="utf-8")
    return active_path


def test_append_env_jsonl_window_stats(tmp_path: Path) -> None:
    active_path = _active(tmp_path)
    env = {
        "n": 10,
        "temp_c": {"min": 21.0, "max": 22.5, "mean": 21.8},
        "rh_pct": {"min": 40.0, "max": 45.0, "mean": 42.1},
    }
    out = append_env_jsonl(
        active_path=active_path,
        cam_id="bhvr-cam0",
        ts="2026-10-22T18:00:00Z",
        env=env,
    )
    assert out is not None
    assert (
        append_env_jsonl(
            active_path=active_path,
            cam_id="bhvr-cam9",
            ts="2026-10-22T18:00:00Z",
            env=env,
        )
        is None
    )
    line = json.loads(out.read_text(encoding="utf-8").strip())
    assert line["n"] == 10
    assert line["temp_c"] == {"min": 21.0, "max": 22.5, "mean": 21.8}
    assert line["rh_pct"]["mean"] == 42.1


def test_append_env_jsonl_legacy_scalars(tmp_path: Path) -> None:
    active_path = _active(tmp_path)
    out = append_env_jsonl(
        active_path=active_path,
        cam_id="bhvr-cam0",
        temp_c=22.4,
        rh_pct=41.0,
        ts="2026-10-22T18:00:00Z",
    )
    assert out is not None
    line = json.loads(out.read_text(encoding="utf-8").strip())
    assert line["n"] == 1
    assert line["temp_c"] == {"min": 22.4, "max": 22.4, "mean": 22.4}
    assert line["rh_pct"]["mean"] == 41.0
