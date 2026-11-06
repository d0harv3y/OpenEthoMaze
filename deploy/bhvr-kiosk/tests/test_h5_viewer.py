"""H5 viewer sandbox / tree / pack-now plan (grill MVP)."""

from __future__ import annotations

from pathlib import Path

import pytest

h5py = pytest.importorskip("h5py")

from app import h5_archive, h5_viewer  # noqa: E402


def test_realpath_under_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    outside = tmp_path / "other"
    outside.mkdir()
    f = outside / "x.h5"
    f.write_bytes(b"x")
    with pytest.raises(ValueError, match="escapes"):
        h5_viewer.realpath_under(root, f)


def test_parse_loose_ts_stem() -> None:
    p = h5_viewer.parse_loose_ts_stem("m1__ses__bhvr-cam0__p000")
    assert p is not None
    assert p["subject_id"] == "m1"
    assert p["recording_tag"] == "ses"
    assert p["cam_id"] == "bhvr-cam0"
    assert p["part"] == 0


def test_build_tree_and_parts(tmp_path: Path) -> None:
    h5 = tmp_path / "m1__ses__bhvr-cam0.h5"
    h5_archive.create_cam_h5(h5, attrs={"cam_id": "bhvr-cam0", "subject_id": "m1"})
    ts = tmp_path / "m1__ses__bhvr-cam0__p000.ts"
    ts.write_bytes(b"\x47" * 188 * 8)
    h5_archive.pack_part(h5, part=0, ts_path=ts, delete_loose=False)
    tree = h5_viewer.build_tree(h5)
    assert tree["children"]
    parts = h5_viewer.mpegts_parts(h5)
    assert len(parts) == 1
    assert parts[0]["path"] == "video/mpegts_000"
    detail = h5_viewer.node_detail(h5, "video/mpegts_000")
    assert detail["preview"]["kind"] == "mpegts"


def test_plan_pack_now_skip_and_force(tmp_path: Path) -> None:
    h5 = tmp_path / "m1__ses__c0.h5"
    h5_archive.create_cam_h5(h5, attrs={"cam_id": "c0", "subject_id": "m1"})
    ts0 = tmp_path / "m1__ses__c0__p000.ts"
    ts1 = tmp_path / "m1__ses__c0__p001.ts"
    ts0.write_bytes(b"\x47" * 188 * 4)
    ts1.write_bytes(b"\x47" * 188 * 4)
    h5_archive.pack_part(h5, part=0, ts_path=ts0, delete_loose=False)

    plan = h5_viewer.plan_pack_now(tmp_path, force=False)
    actions = {(i["part"], i["action"]) for i in plan}
    assert (0, "skip") in actions
    assert (1, "pack") in actions

    plan_f = h5_viewer.plan_pack_now(tmp_path, force=True)
    assert all(i["action"] == "pack" for i in plan_f)


def test_pack_part_skip_if_exists(tmp_path: Path) -> None:
    h5 = tmp_path / "a__ses__c.h5"
    h5_archive.create_cam_h5(h5, attrs={"cam_id": "c", "subject_id": "a"})
    ts = tmp_path / "a__ses__c__p000.ts"
    ts.write_bytes(b"\x47" * 188 * 4)
    h5_archive.pack_part(h5, part=0, ts_path=ts, delete_loose=False)
    r = h5_archive.pack_part(
        h5, part=0, ts_path=ts, delete_loose=True, skip_if_exists=True
    )
    assert r["ok"] and r.get("skipped")
    assert ts.exists()  # not deleted on skip


def test_is_active_session_dir(tmp_path: Path) -> None:
    folder = tmp_path / "ses-20260101T000000Z"
    folder.mkdir()
    active = tmp_path / ".active_session.json"
    active.write_text(
        '{"folder": ' + json_dumps(str(folder)) + "}",
        encoding="utf-8",
    )
    assert h5_viewer.is_active_session_dir(folder, active) is True
    other = tmp_path / "ses-other"
    other.mkdir()
    assert h5_viewer.is_active_session_dir(other, active) is False


def json_dumps(s: str) -> str:
    import json

    return json.dumps(s)
