"""GET /orm/health — service metadata (Phase B4)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

from ..llm import is_llm_configured, is_llm_loaded
from ..yolo import is_yolo_configured, is_yolo_loaded

if TYPE_CHECKING:
    from flask import Blueprint


def get_maze_version() -> str:
    """Installed package version from distribution metadata (``pyproject.toml``)."""
    try:
        return version("maze")
    except PackageNotFoundError:
        return "unknown"


def register_health_routes(bp: Blueprint) -> None:
    from flask import current_app, jsonify

    @bp.get("/health")
    def orm_health():
        config = current_app.config["LOCAL_SERVICE_CONFIG"]
        return jsonify(
            {
                "version": get_maze_version(),
                "data_root": str(config.data_root),
                "extra_roots": [str(p) for p in config.extra_roots],
                "llm_loaded": is_llm_loaded(),
                "llm_configured": is_llm_configured(config),
                "yolo_loaded": is_yolo_loaded(),
                "yolo_configured": is_yolo_configured(),
            }
        )
