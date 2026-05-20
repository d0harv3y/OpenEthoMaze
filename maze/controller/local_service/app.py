"""Flask application factory for the unified local HTTP service (Phase B)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import LocalServiceConfig
from .routes import create_orm_blueprint

if TYPE_CHECKING:
    from flask import Flask


def create_local_app(config: LocalServiceConfig) -> Flask:
    """Build Flask app: h5web + h5grove at ``/`` and ``/api/*``, ``/orm/*`` service routes."""
    from flask import Flask

    from maze.controller.acquisition.h5web_server import (
        get_h5web_static_dir,
        register_h5web_routes,
    )

    static_dir = get_h5web_static_dir()
    if static_dir is None:
        raise RuntimeError(
            "h5web static build not found. Build from maze/controller/web/h5web: "
            "npm install && npm run build"
        )

    app = Flask("maze-local-service")
    register_h5web_routes(app, h5_base_dir=config.data_root, static_dir=static_dir)
    app.register_blueprint(create_orm_blueprint())
    app.config["LOCAL_SERVICE_CONFIG"] = config
    return app
