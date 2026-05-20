"""h5web Flask factory smoke tests (Phase B PR-B1).

Requires: core + dev (``h5grove[flask]`` in core dependencies; CI: ``uv sync --extra dev``).
Covers ``register_h5web_routes`` / ``create_app`` used by GUI and ``create_local_app``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from flask import Flask

from maze.controller.acquisition.h5web_server import (
    create_app,
    get_h5web_static_dir,
    register_h5web_routes,
)

EXPECTED_H5WEB_RULES = frozenset(
    {
        "/",
        "/api/",
        "/api/meta",
        "/api/data",
        "/api/attr",
        "/api/stats",
        "/assets/<path:path>",
        "/favicon.ico",
    }
)


@pytest.fixture
def minimal_h5web_static(tmp_path: Path) -> tuple[Path, Path]:
    """Minimal static tree and HDF5 base dir for route registration tests."""
    h5_base = tmp_path / "cohort"
    h5_base.mkdir()
    static_dir = tmp_path / "h5web_dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!DOCTYPE html><html></html>", encoding="utf-8")
    (static_dir / "assets").mkdir()
    (static_dir / "favicon.ico").write_bytes(b"\x00")
    return h5_base, static_dir


def _rule_set(app: Flask) -> frozenset[str]:
    return frozenset(rule.rule for rule in app.url_map.iter_rules())


def test_get_h5web_static_dir_resolves_controller_web_dist(repo_root: Path) -> None:
    static = get_h5web_static_dir()
    expected = repo_root / "maze" / "controller" / "web" / "h5web_dist"
    if (expected / "index.html").is_file():
        assert static == expected
    else:
        assert static is None


def test_register_h5web_routes_registers_expected_rules(
    minimal_h5web_static: tuple[Path, Path],
) -> None:
    h5_base, static_dir = minimal_h5web_static
    app = Flask("test-h5web")
    register_h5web_routes(app, h5_base_dir=h5_base, static_dir=static_dir)

    assert EXPECTED_H5WEB_RULES <= _rule_set(app)
    assert app.config["H5_BASE_DIR"] == str(h5_base.resolve())


def test_create_app_matches_register_h5web_routes(
    minimal_h5web_static: tuple[Path, Path],
) -> None:
    h5_base, static_dir = minimal_h5web_static
    app = create_app(h5_base, static_dir)

    assert EXPECTED_H5WEB_RULES <= _rule_set(app)
    assert app.config["H5_BASE_DIR"] == str(h5_base.resolve())


def test_create_app_serves_index(minimal_h5web_static: tuple[Path, Path]) -> None:
    h5_base, static_dir = minimal_h5web_static
    app = create_app(h5_base, static_dir)
    client = app.test_client()

    response = client.get("/")
    assert response.status_code == 200
    assert b"html" in response.data.lower()


def test_register_h5web_routes_api_root_responds(minimal_h5web_static: tuple[Path, Path]) -> None:
    h5_base, static_dir = minimal_h5web_static
    app = Flask("test-h5web-api")
    register_h5web_routes(app, h5_base_dir=h5_base, static_dir=static_dir)
    client = app.test_client()
    response = client.get("/api/")
    assert response.status_code != 500
