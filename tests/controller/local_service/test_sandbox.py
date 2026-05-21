"""Path sandbox and glob_safe unit tests (Phase B PR-B2, extended PR-B7).

Requires: core + dev (see ``fixtures.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["controller.local_service.fixtures"]

from maze.controller.local_service.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    LocalServiceConfig,
    build_config,
)
from maze.controller.local_service.glob_safe import (
    GlobLimitError,
    GlobTimeoutError,
    glob_safe,
)
from maze.controller.local_service.sandbox import (
    PathNotAllowedError,
    PathSandbox,
    SymlinkNotAllowedError,
)


def test_config_defaults(service_config: LocalServiceConfig) -> None:
    assert service_config.host == DEFAULT_HOST
    assert service_config.port == DEFAULT_PORT
    assert service_config.max_globs >= 1
    assert service_config.max_matches >= 1
    assert service_config.glob_timeout_seconds > 0


def test_resolve_relative_under_data_root(sandbox: PathSandbox, data_tree: tuple[Path, Path]) -> None:
    data_root, _ = data_tree
    resolved = sandbox.resolve("cohort/trials.h5", must_exist=True)
    assert resolved == (data_root / "cohort" / "trials.h5").resolve()


def test_resolve_rejects_dotdot(sandbox: PathSandbox) -> None:
    with pytest.raises(PathNotAllowedError, match="\\.\\."):
        sandbox.resolve("../outside/secret.h5")


def test_resolve_rejects_dotdot_in_relative_parts(sandbox: PathSandbox, data_tree: tuple[Path, Path]) -> None:
    data_root, _ = data_tree
    with pytest.raises(PathNotAllowedError, match="\\.\\."):
        sandbox.resolve("cohort/../outside/secret.h5", base=data_root)


def test_resolve_rejects_absolute_outside_root(
    sandbox: PathSandbox, data_tree: tuple[Path, Path]
) -> None:
    _data_root, outside = data_tree
    with pytest.raises(PathNotAllowedError, match="outside allowed roots"):
        sandbox.resolve(outside / "secret.h5")


def test_resolve_rejects_missing_path_when_must_exist(
    sandbox: PathSandbox, data_tree: tuple[Path, Path]
) -> None:
    with pytest.raises(PathNotAllowedError, match="does not exist"):
        sandbox.resolve("cohort/missing.h5", must_exist=True)


def test_resolve_allows_extra_root(service_config: LocalServiceConfig, data_tree: tuple[Path, Path]) -> None:
    _data_root, outside = data_tree
    sb = service_config.sandbox()
    resolved = sb.resolve(outside / "secret.h5", must_exist=True)
    assert resolved == (outside / "secret.h5").resolve()


def test_symlink_inside_root_allowed(sandbox: PathSandbox, data_tree: tuple[Path, Path]) -> None:
    data_root, _ = data_tree
    target = data_root / "cohort" / "trials.h5"
    link = data_root / "link.h5"
    try:
        PathSandbox.try_symlink(link, target)
    except OSError as exc:
        pytest.skip(f"symlinks not available: {exc}")

    resolved = sandbox.resolve(link, must_exist=True)
    assert resolved == target.resolve()


def test_symlink_outside_root_rejected(sandbox: PathSandbox, data_tree: tuple[Path, Path]) -> None:
    data_root, outside = data_tree
    link = data_root / "escape.h5"
    try:
        PathSandbox.try_symlink(link, outside / "secret.h5")
    except OSError as exc:
        pytest.skip(f"symlinks not available: {exc}")

    with pytest.raises(SymlinkNotAllowedError, match="escapes allowed root"):
        sandbox.resolve(link)


def test_build_config_rejects_missing_root(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(ValueError, match="existing directory"):
        build_config(missing)


def test_sandbox_requires_existing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(ValueError, match="existing directory"):
        PathSandbox([missing])


def test_glob_safe_finds_h5_under_root(sandbox: PathSandbox, data_tree: tuple[Path, Path]) -> None:
    data_root, _ = data_tree
    matches = glob_safe(
        sandbox,
        ["**/*.h5"],
        max_globs=4,
        max_matches=50,
        timeout_seconds=5.0,
    )
    assert (data_root / "cohort" / "trials.h5").resolve() in matches
    assert all(m.is_relative_to(data_root.resolve()) for m in matches)


def test_glob_safe_rejects_dotdot_pattern(sandbox: PathSandbox) -> None:
    with pytest.raises(GlobLimitError, match="\\.\\."):
        glob_safe(
            sandbox,
            ["../**/*.h5"],
            max_globs=4,
            max_matches=50,
            timeout_seconds=5.0,
        )


def test_glob_safe_enforces_max_globs(sandbox: PathSandbox) -> None:
    patterns = ["*.h5", "**/*.txt", "**/*.h5"]
    with pytest.raises(GlobLimitError, match="glob patterns"):
        glob_safe(
            sandbox,
            patterns,
            max_globs=2,
            max_matches=50,
            timeout_seconds=5.0,
        )


def test_glob_safe_enforces_max_matches(sandbox: PathSandbox) -> None:
    with pytest.raises(GlobLimitError, match="match cap"):
        glob_safe(
            sandbox,
            ["**/*"],
            max_globs=4,
            max_matches=1,
            timeout_seconds=5.0,
        )


def test_glob_safe_timeout(sandbox: PathSandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    glob_mod = importlib.import_module("maze.controller.local_service.glob_safe")
    clock = [1000.0]

    def fake_monotonic() -> float:
        clock[0] += 2.0
        return clock[0]

    monkeypatch.setattr(glob_mod.time, "monotonic", fake_monotonic)
    with pytest.raises(GlobTimeoutError):
        glob_safe(
            sandbox,
            ["**/*"],
            max_globs=4,
            max_matches=200,
            timeout_seconds=1.0,
        )


def test_glob_safe_does_not_escape_via_symlink(
    sandbox: PathSandbox, data_tree: tuple[Path, Path]
) -> None:
    data_root, outside = data_tree
    link = data_root / "outside_link.h5"
    try:
        PathSandbox.try_symlink(link, outside / "secret.h5")
    except OSError as exc:
        pytest.skip(f"symlinks not available: {exc}")

    matches = glob_safe(
        sandbox,
        ["**/*.h5"],
        max_globs=4,
        max_matches=50,
        timeout_seconds=5.0,
    )
    assert (outside / "secret.h5").resolve() not in matches
