"""H5 session archive v0 (chunk pack + verify delete)."""

from __future__ import annotations

from pathlib import Path

import pytest

h5py = pytest.importorskip("h5py")
np = pytest.importorskip("numpy")

from app import h5_archive  # noqa: E402
from app.capture_sink import CaptureSink  # noqa: E402


def test_cam_h5_path_always_has_tag(tmp_path: Path) -> None:
    assert (
        h5_archive.cam_h5_path(tmp_path, "m1", "bhvr-cam0")
        == tmp_path / "m1__ses__bhvr-cam0.h5"
    )
    assert (
        h5_archive.cam_h5_path(tmp_path, "m1", "bhvr-cam0", recording_tag="pre")
        == tmp_path / "m1__pre__bhvr-cam0.h5"
    )


def test_capture_sink_rotate(tmp_path: Path) -> None:
    p0 = tmp_path / "p000.ts"
    p1 = tmp_path / "p001.ts"
    sink = CaptureSink(p0)
    sink.write(b"AAAA")
    closed = sink.rotate(p1)
    assert closed == p0
    sink.write(b"BBBB")
    sink.close()
    assert p0.read_bytes() == b"AAAA"
    assert p1.read_bytes() == b"BBBB"


def test_pack_part_creates_dataset_and_deletes_loose(tmp_path: Path) -> None:
    h5 = tmp_path / "sub__cam.h5"
    h5_archive.create_cam_h5(h5, attrs={"cam_id": "bhvr-cam0", "subject_id": "sub"})
    ts = tmp_path / "sub__cam__p000.ts"
    pts = tmp_path / "sub__cam__p000.pts"
    payload = b"\x00" * 188 * 20  # fake TS-ish size
    ts.write_bytes(payload)
    pts.write_text("0\n33.3\n66.6\n", encoding="utf-8")
    result = h5_archive.pack_part(
        h5,
        part=0,
        ts_path=ts,
        pts_path=pts,
        fps_summary={"achieved_fps": 30.0, "pts_frames": 3},
        attrs={"roll_reason": "stop"},
        delete_loose=True,
    )
    assert result["ok"] is True
    assert not ts.exists()
    assert not pts.exists()
    with h5py.File(h5, "r") as f:
        assert "video/mpegts_000" in f
        assert f["video/mpegts_000"].shape == (len(payload),)
        assert "description" in f["video/mpegts_000"].attrs
        assert "video/pts_000" in f
        assert f["video/pts_000"].shape[0] == 3
        assert float(f["video/pts_000"][0]) == 0.0
        assert "description" in f["video/pts_000"].attrs
        assert "logs" in f


def test_pack_part_folds_sidecars(tmp_path: Path) -> None:
    h5 = tmp_path / "test__ses__bhvr-cam0.h5"
    h5_archive.create_cam_h5(
        h5, attrs={"cam_id": "bhvr-cam0", "subject_id": "test"}
    )
    stem = "test__ses__bhvr-cam0__p000"
    ts = tmp_path / f"{stem}.ts"
    pts = tmp_path / f"{stem}.pts"
    cap = tmp_path / f"{stem}_capture.log"
    remux = tmp_path / f"{stem}_remux.log"
    fps = tmp_path / f"{stem}_fps.json"
    env = tmp_path / "test__bhvr-cam0_env.jsonl"
    pts_full = tmp_path / ".bhvr-cam0_pts_full.pts"
    stop = tmp_path / "stop_log.json"
    ts.write_bytes(b"\x47" * 188 * 10)
    pts.write_text("0\n33\n66\n", encoding="utf-8")
    cap.write_text("capture hello\n", encoding="utf-8")
    remux.write_text("remux warn\n", encoding="utf-8")
    fps.write_text('{"achieved_fps": 29.5}\n', encoding="utf-8")
    env.write_text('{"ts":"x","temp_c":{"mean":35}}\n', encoding="utf-8")
    pts_full.write_text("0\n33\n66\n99\n", encoding="utf-8")
    stop.write_text('["OK stop"]\n', encoding="utf-8")

    result = h5_archive.pack_part(
        h5,
        part=0,
        ts_path=ts,
        pts_path=pts,
        fps_summary={"achieved_fps": 29.5},
        attrs={"cam_id": "bhvr-cam0", "subject_id": "test", "roll_reason": "stop"},
        delete_loose=True,
        folder=tmp_path,
        cam_id="bhvr-cam0",
        subject_id="test",
        pack_session_sidecars=True,
    )
    assert result["ok"] is True
    assert not ts.exists()
    assert not pts.exists()
    assert not cap.exists()
    assert not remux.exists()
    assert not fps.exists()
    assert not env.exists()
    assert not pts_full.exists()
    assert stop.exists()  # loose kept for operators
    with h5py.File(h5, "r") as f:
        assert "logs/capture_000" in f
        assert (
            bytes(f["logs/capture_000"][()])
            .decode("utf-8")
            .replace("\r\n", "\n")
            == "capture hello\n"
        )
        assert "logs/remux_000" in f
        assert "description" in f["logs/remux_000"].attrs
        assert "logs/env_jsonl" in f
        assert "description" in f["logs/env_jsonl"].attrs
        assert "logs/pts_full" in f
        assert "fps_file_json" in f["video/mpegts_000"].attrs
        assert "stop_log_json" in f.attrs


def test_pack_skips_empty_remux_but_deletes(tmp_path: Path) -> None:
    h5 = tmp_path / "m__ses__c.h5"
    h5_archive.create_cam_h5(h5, attrs={"cam_id": "c", "subject_id": "m"})
    stem = "m__ses__c__p000"
    ts = tmp_path / f"{stem}.ts"
    remux = tmp_path / f"{stem}_remux.log"
    ts.write_bytes(b"\x47" * 188 * 4)
    remux.write_bytes(b"")
    result = h5_archive.pack_part(
        h5, part=0, ts_path=ts, delete_loose=True, folder=tmp_path
    )
    assert result["ok"] is True
    assert not remux.exists()
    with h5py.File(h5, "r") as f:
        assert "logs/remux_000" not in f


def test_slice_pts_file(tmp_path: Path) -> None:
    full = tmp_path / "full.pts"
    part = tmp_path / "part.pts"
    full.write_text("0\n10\n20\n30\n40\n", encoding="utf-8")
    n, nxt = h5_archive.slice_pts_file(full, part, start_index=2)
    assert n == 3 and nxt == 5
    assert part.read_text(encoding="utf-8").strip().splitlines() == ["20", "30", "40"]
