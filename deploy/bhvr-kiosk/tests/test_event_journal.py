from __future__ import annotations

from pathlib import Path

from app.event_journal import append_event, recent_events


def test_append_and_recent(tmp_path: Path) -> None:
    a = append_event(
        tmp_path,
        session_id="page-abc",
        kind="ui.start_ok",
        detail={"camera_ids": ["bhvr-cam0"]},
        source="ui",
    )
    assert a["ok"] is True
    assert a["bytes"] > 0
    snap = recent_events(tmp_path, session_id="page-abc", limit=10)
    assert snap["session_id"] == "page-abc"
    assert len(snap["events"]) == 1
    assert snap["events"][0]["kind"] == "ui.start_ok"


def test_prune_keeps_newest(tmp_path: Path) -> None:
    import app.event_journal as ej

    old = ej.MAX_SESSIONS
    try:
        ej.MAX_SESSIONS = 3
        for i in range(5):
            append_event(tmp_path, session_id=f"s{i}", kind="t", detail={"i": i})
        files = list((tmp_path / ej.JOURNAL_DIRNAME).glob("*.jsonl"))
        assert len(files) <= 3
    finally:
        ej.MAX_SESSIONS = old
