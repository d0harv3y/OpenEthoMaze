"""Local service Flask app and CLI (Phase B PR-B3).

Requires: core + dev (see ``fixtures.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["controller.local_service.fixtures"]

from maze.controller.local_service import __main__ as cli
from maze.controller.local_service.app import create_local_app
from maze.controller.local_service.config import build_config
from maze.controller.local_service.routes import create_orm_blueprint


def test_create_local_app_serves_index(
    minimal_h5web_static: tuple[Path, Path],
    patch_h5web_static: Path,
) -> None:
    h5_base, _static = minimal_h5web_static
    config = build_config(h5_base)
    app = create_local_app(config)
    client = app.test_client()

    response = client.get("/")
    assert response.status_code == 200
    assert b"html" in response.data.lower()
    assert app.config["H5_BASE_DIR"] == str(h5_base.resolve())
    assert app.config["LOCAL_SERVICE_CONFIG"] == config


def test_create_local_app_registers_orm_blueprint(
    minimal_h5web_static: tuple[Path, Path],
    patch_h5web_static: Path,
) -> None:
    h5_base, _static = minimal_h5web_static
    app = create_local_app(build_config(h5_base))
    assert "orm" in app.blueprints
    assert app.blueprints["orm"].url_prefix == "/orm"


def test_create_orm_blueprint_registers_orm_routes() -> None:
    from flask import Flask

    app = Flask("test")
    app.register_blueprint(create_orm_blueprint())
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/orm/health" in rules
    assert "/orm/discover" in rules
    assert "/orm/detect" in rules


def test_create_local_app_raises_without_static_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maze.controller.acquisition.h5web_server as h5web_server

    monkeypatch.setattr(h5web_server, "get_h5web_static_dir", lambda: None)
    config = build_config(tmp_path)
    with pytest.raises(RuntimeError, match="h5web static build not found"):
        create_local_app(config)


def test_main_requires_data_root() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code != 0


def test_main_run_server_uses_config(
    minimal_h5web_static: tuple[Path, Path],
    patch_h5web_static: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h5_base, _static = minimal_h5web_static
    monkeypatch.setattr(cli, "_require_runtime_dependencies", lambda: None)

    served: list[tuple[str, int]] = []

    def fake_run_server(config: object) -> None:
        from maze.controller.local_service.config import LocalServiceConfig

        assert isinstance(config, LocalServiceConfig)
        served.append((config.host, config.port))

    monkeypatch.setattr(cli, "run_server", fake_run_server)

    cli.main(["--data-root", str(h5_base), "--host", "127.0.0.1", "--port", "9999"])
    assert served == [("127.0.0.1", 9999)]


def test_missing_dependency_messages_without_waitress(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "waitress":
            raise ImportError("no waitress")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    messages = cli._missing_dependency_messages()
    assert any("waitress" in msg for msg in messages)
