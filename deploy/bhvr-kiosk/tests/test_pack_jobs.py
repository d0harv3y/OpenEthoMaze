"""Round A final-pack queue (Stop S2+)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from app import pack_jobs


def test_enqueue_and_snapshot(tmp_path: Path) -> None:
    h5 = tmp_path / "m1__ses__cam.h5"
    ts = tmp_path / "part.ts"
    ts.write_bytes(b"x" * 100)

    def pack_fn(h5_path, **kwargs):  # noqa: ANN001
        assert h5_path == h5
        return {"ok": True, "bytes": 100}

    jid = pack_jobs.enqueue(
        cam_id="bhvr-cam0",
        folder=str(tmp_path),
        h5_path=h5,
        part=0,
        ts_path=ts,
        pts_path=None,
        fps_summary=None,
        attrs={"roll_reason": "stop"},
        pack_fn=pack_fn,
    )
    assert jid
    for _ in range(50):
        snap = pack_jobs.snapshot()
        if not snap["pending"] and snap["ok"] >= 1:
            break
        time.sleep(0.05)
    snap = pack_jobs.snapshot()
    assert snap["pending"] is False
    assert snap["ok"] >= 1
    assert snap["state"] == "ok"
    assert "PACK OK" in snap["label"]


def test_pending_while_running(tmp_path: Path) -> None:
    gate = threading.Event()

    def slow_pack(h5_path, **kwargs):  # noqa: ANN001
        gate.wait(timeout=2.0)
        return {"ok": True, "bytes": 1}

    ts = tmp_path / "a.ts"
    ts.write_bytes(b"abc")
    pack_jobs.enqueue(
        cam_id="c1",
        folder=str(tmp_path),
        h5_path=tmp_path / "a.h5",
        part=0,
        ts_path=ts,
        pts_path=None,
        fps_summary=None,
        attrs={},
        pack_fn=slow_pack,
    )
    assert pack_jobs.pending() is True
    gate.set()
    for _ in range(50):
        if not pack_jobs.pending():
            break
        time.sleep(0.05)
    assert pack_jobs.pending() is False
