"""Lightweight kpMS optional-dependency probe (no JAX import)."""

from __future__ import annotations


def is_kpms_available() -> bool:
    """True when ``keypoint_moseq`` is installed (``uv sync --extra kpms``)."""
    try:
        import keypoint_moseq  # noqa: F401
    except ImportError:
        return False
    return True
