"""Sandbox enforcement via Flask client (Phase B PR-B7).

Requires: core + dev (see ``fixtures.py``). No GGUF, GPU, or YOLO weights.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["tests.controller.local_service.fixtures"]


def test_post_discover_keyword_never_returns_outside_data_root(local_app) -> None:
    client = local_app.test_client()
    response = client.post(
        "/orm/discover",
        json={"query": "h5 files", "limit": 50},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mode"] == "keyword"
    for match in payload["matches"]:
        path = Path(match)
        assert not path.is_absolute()
        assert "secret.h5" not in match.replace("\\", "/")


def test_post_discover_rejects_dotdot_glob_via_http(local_app) -> None:
    client = local_app.test_client()
    response = client.post(
        "/orm/discover",
        json={"query": "h5", "limit": 10},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert all(".." not in g for g in payload["globs"])


def test_post_detect_rejects_video_outside_data_root(local_app, data_tree: tuple[Path, Path]) -> None:
    _data_root, outside = data_tree
    client = local_app.test_client()
    response = client.post(
        "/orm/detect",
        json={"video_path": str(outside / "secret.h5"), "frame_index": 0},
    )
    assert response.status_code in (400, 503)
    if response.status_code == 400:
        assert "not allowed" in response.get_json()["error"].lower()


def test_post_discover_empty_query_400(local_app) -> None:
    client = local_app.test_client()
    response = client.post("/orm/discover", json={"query": "  "})
    assert response.status_code == 400
