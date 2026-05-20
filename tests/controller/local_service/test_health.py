"""GET /orm/health (Phase B PR-B4).

Requires: core + dev (see ``fixtures.py``).
"""

from __future__ import annotations

import pytest

pytest_plugins = ["tests.controller.local_service.fixtures"]

from maze.controller.local_service.routes.health import get_maze_version

HEALTH_JSON_KEYS = frozenset(
    {
        "version",
        "data_root",
        "extra_roots",
        "llm_loaded",
        "llm_configured",
        "yolo_loaded",
        "yolo_configured",
    }
)


def test_get_maze_version_is_installed_distribution() -> None:
    ver = get_maze_version()
    assert ver not in ("", "unknown")


def test_orm_health_returns_expected_json(local_app_with_extra_roots) -> None:
    client = local_app_with_extra_roots.test_client()
    response = client.get("/orm/health")

    assert response.status_code == 200
    assert response.content_type.startswith("application/json")
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert set(payload.keys()) == HEALTH_JSON_KEYS
    assert payload["llm_loaded"] is False
    assert payload["yolo_loaded"] is False
    assert payload["yolo_configured"] is False
    assert payload["version"] == get_maze_version()
    config = local_app_with_extra_roots.config["LOCAL_SERVICE_CONFIG"]
    assert payload["data_root"] == str(config.data_root)
    assert payload["extra_roots"] == [str(p) for p in config.extra_roots]
