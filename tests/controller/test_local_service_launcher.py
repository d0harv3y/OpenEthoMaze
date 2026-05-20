"""local_service subprocess launcher (Phase B PR-B8).

Requires: core + dev only (no waitress spawn in CI — Popen is mocked).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from maze.controller.local_service_launcher import (
    build_launch_command,
    remember_data_root,
    reset_launcher_state,
    spawn_local_service,
    suggested_data_root,
    waitress_unavailable_message,
)
from maze.controller.local_service.config import DEFAULT_HOST, DEFAULT_PORT


@pytest.fixture(autouse=True)
def _clear_launcher_state() -> None:
    reset_launcher_state()
    yield
    reset_launcher_state()


def test_build_launch_command_uses_module_and_data_root(tmp_path: Path) -> None:
    data_root = tmp_path / "cohort"
    data_root.mkdir()
    remember_data_root(data_root)

    argv = build_launch_command(
        data_root,
        host="127.0.0.1",
        port=9999,
        python_executable="/usr/bin/python",
    )

    assert argv == [
        "/usr/bin/python",
        "-m",
        "maze.controller.local_service",
        "--data-root",
        str(data_root.resolve()),
        "--host",
        "127.0.0.1",
        "--port",
        "9999",
    ]


def test_suggested_data_root_prefers_last_used(tmp_path: Path) -> None:
    first = tmp_path / "first"
    first.mkdir()
    second = tmp_path / "second"
    second.mkdir()
    remember_data_root(first)

    assert suggested_data_root(second) == first.resolve()


def test_suggested_data_root_falls_back_to_output_dir(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    assert suggested_data_root(output) == output.resolve()


def test_spawn_local_service_invokes_popen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    calls: list[list[str]] = []

    class FakePopen:
        pid = 4242

        def __init__(self, command: list[str], **kwargs: object) -> None:
            calls.append(command)

        def poll(self) -> None:
            return None

    monkeypatch.setattr(
        "maze.controller.local_service_launcher.is_waitress_available",
        lambda: True,
    )

    process = spawn_local_service(
        data_root,
        host=DEFAULT_HOST,
        port=8765,
        python_executable="/venv/python",
        popen=FakePopen,
    )

    assert process.pid == 4242
    assert len(calls) == 1
    assert calls[0][0:4] == ["/venv/python", "-m", "maze.controller.local_service", "--data-root"]
    assert calls[0][4] == str(data_root.resolve())


def test_spawn_raises_when_waitress_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setattr(
        "maze.controller.local_service_launcher.is_waitress_available",
        lambda: False,
    )

    with pytest.raises(RuntimeError, match="waitress"):
        spawn_local_service(data_root)

    assert "local-service" in waitress_unavailable_message()


def test_spawn_rejects_second_start_while_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()

    class FakePopen:
        pid = 1

        def __init__(self, command: list[str], **kwargs: object) -> None:
            pass

        def poll(self) -> None:
            return None

    monkeypatch.setattr(
        "maze.controller.local_service_launcher.is_waitress_available",
        lambda: True,
    )
    spawn_local_service(data_root, popen=FakePopen)

    with pytest.raises(RuntimeError, match="already running"):
        spawn_local_service(data_root, popen=FakePopen)
