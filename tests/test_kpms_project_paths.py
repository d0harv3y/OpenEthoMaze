"""kpMS per-stream project directory layout (Phase T4c)."""

from __future__ import annotations

from pathlib import Path

from maze.kpms.project_paths import default_kpms_root, resolve_kpms_project_dir


def test_default_kpms_root() -> None:
    assert default_kpms_root("/data/out") == Path("/data/out/kpms")


def test_resolve_appends_stream_subdir() -> None:
    root = Path("/proj/kpms")
    assert resolve_kpms_project_dir(root, "blob") == Path("/proj/kpms/blob")
    assert resolve_kpms_project_dir(root, "fused") == Path("/proj/kpms/fused")


def test_resolve_idempotent_when_already_stream_specific() -> None:
    already = Path("/proj/kpms/anatomical")
    assert resolve_kpms_project_dir(already, "blob") == already
