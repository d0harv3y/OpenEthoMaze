"""Shared pytest fixtures for ``tests/controller/local_service/``.

Loaded via repo-root ``conftest.py`` →
``pytest_plugins = ["controller.local_service.fixtures"]`` (requires
``pythonpath = ["tests", "."]`` in ``pyproject.toml``). Do not use
``tests.controller.*`` — site-packages may ship a conflicting ``tests`` package.
Do not add nested ``conftest.py`` here (pytest 9+ and ``from conftest import …``
in top-level tests).

Dependency groups (GitHub CI: ``uv sync --extra dev``):
- Fixtures here: **core + dev** (``h5grove[flask]``, ``opencv-python``; no
  ``local-service``, GGUF, or ``.pt`` weights).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from maze.controller.local_service.app import create_local_app
from maze.controller.local_service.config import LocalServiceConfig, build_config
from maze.controller.local_service.sandbox import PathSandbox


@pytest.fixture
def data_tree(tmp_path: Path) -> tuple[Path, Path]:
    """``(data_root, outside_dir)`` — sibling outside tree for escape tests."""
    data_root = tmp_path / "data"
    data_root.mkdir(exist_ok=True)
    (data_root / "cohort").mkdir(exist_ok=True)
    (data_root / "cohort" / "trials.h5").write_bytes(b"h5")
    (data_root / "cohort" / "notes.txt").write_text("ok", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir(exist_ok=True)
    (outside / "secret.h5").write_bytes(b"no")
    return data_root, outside


@pytest.fixture
def sandbox(data_tree: tuple[Path, Path]) -> PathSandbox:
    return PathSandbox([data_tree[0]])


@pytest.fixture
def service_config(data_tree: tuple[Path, Path]) -> LocalServiceConfig:
    data_root, outside = data_tree
    return build_config(data_root, extra_roots=[outside])


# Minimal 1×1 PNG (no cv2 required to build test images).
TINY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def tiny_png() -> bytes:
    return TINY_PNG_BYTES


@pytest.fixture
def mock_decode_image_bgr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid relying on ``cv2.imdecode`` for synthetic PNG bytes in unit tests."""
    import numpy as np

    import maze.controller.local_service.detect as detect_mod

    monkeypatch.setattr(
        detect_mod,
        "_decode_image_bytes",
        lambda _data: np.zeros((4, 4, 3), dtype=np.uint8),
    )


@pytest.fixture
def minimal_h5web_static(tmp_path: Path) -> tuple[Path, Path]:
    """``(data_root, static_dir)`` for Flask app tests (minimal h5web_dist)."""
    data_root = tmp_path / "data"
    data_root.mkdir(exist_ok=True)
    (data_root / "cohort").mkdir(exist_ok=True)
    (data_root / "cohort" / "trials.h5").write_bytes(b"h5")
    outside = data_root.parent / "outside"
    outside.mkdir(exist_ok=True)
    (outside / "secret.h5").write_bytes(b"no")
    static_dir = tmp_path / "h5web_dist"
    static_dir.mkdir(exist_ok=True)
    (static_dir / "index.html").write_text("<!DOCTYPE html><html></html>", encoding="utf-8")
    (static_dir / "assets").mkdir()
    (static_dir / "favicon.ico").write_bytes(b"\x00")
    return data_root, static_dir


@pytest.fixture
def patch_h5web_static(minimal_h5web_static: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch):
    """Patch ``get_h5web_static_dir`` to the minimal static tree."""
    import maze.controller.acquisition.h5web_server as h5web_server

    _data_root, static_dir = minimal_h5web_static
    monkeypatch.setattr(h5web_server, "get_h5web_static_dir", lambda: static_dir)
    return static_dir


@pytest.fixture
def local_app(
    minimal_h5web_static: tuple[Path, Path],
    patch_h5web_static: Path,
) -> object:
    """``create_local_app`` with ``data_root`` only (no extra roots)."""
    data_root, _static = minimal_h5web_static
    return create_local_app(build_config(data_root))


@pytest.fixture
def local_app_with_extra_roots(
    minimal_h5web_static: tuple[Path, Path],
    patch_h5web_static: Path,
) -> object:
    """``create_local_app`` with ``data_root`` plus sibling ``outside/`` root."""
    data_root, _static = minimal_h5web_static
    outside = data_root.parent / "outside"
    return create_local_app(build_config(data_root, extra_roots=[outside]))
