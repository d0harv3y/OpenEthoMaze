"""ORM Flask blueprint factory (Phase B)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .detect import register_detect_routes
from .discover import register_discover_routes
from .health import register_health_routes

if TYPE_CHECKING:
    from flask import Blueprint


def create_orm_blueprint() -> Blueprint:
    """Blueprint for ``/orm/*`` routes (health, discover, detect)."""
    from flask import Blueprint

    bp = Blueprint("orm", __name__, url_prefix="/orm")
    register_health_routes(bp)
    register_discover_routes(bp)
    register_detect_routes(bp)
    return bp
