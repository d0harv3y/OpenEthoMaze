"""Spawn ``maze-local-service`` in a subprocess (Phase B8).

Data-root default (rescue_plan open decision #3): **session last-used directory**,
else the acquisition GUI **output folder**, else the user picks a folder in a dialog.
The Qt app never loads LLM/YOLO in-process.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

from maze.controller.local_service.config import DEFAULT_HOST, DEFAULT_PORT

_LAST_DATA_ROOT: Path | None = None
_ACTIVE_PROCESS: subprocess.Popen[str] | None = None

WAITRESS_INSTALL_HINT = "uv sync --extra local-service"


def is_waitress_available() -> bool:
    """True when the ``waitress`` package is importable (``local-service`` extra)."""
    try:
        import waitress  # noqa: F401
    except ImportError:
        return False
    return True


def waitress_unavailable_message() -> str:
    return f"local ORM service requires waitress ({WAITRESS_INSTALL_HINT})"


def suggested_data_root(output_dir: Path | str | None) -> Path | None:
    """Directory to pre-select in the folder dialog."""
    if _LAST_DATA_ROOT is not None and _LAST_DATA_ROOT.is_dir():
        return _LAST_DATA_ROOT
    if output_dir:
        candidate = Path(output_dir).expanduser().resolve()
        if candidate.is_dir():
            return candidate
    return None


def remember_data_root(data_root: Path) -> Path:
    """Store last successful data root for this process (session memory only)."""
    global _LAST_DATA_ROOT
    resolved = data_root.expanduser().resolve()
    _LAST_DATA_ROOT = resolved
    return resolved


def build_launch_command(
    data_root: Path,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    python_executable: str | None = None,
) -> list[str]:
    """Argv for ``python -m maze.controller.local_service`` (no shell)."""
    exe = python_executable or sys.executable
    resolved = data_root.expanduser().resolve()
    return [
        exe,
        "-m",
        "maze.controller.local_service",
        "--data-root",
        str(resolved),
        "--host",
        host,
        "--port",
        str(port),
    ]


def is_service_running() -> bool:
    """True if a launcher-spawned subprocess is still running."""
    return _ACTIVE_PROCESS is not None and _ACTIVE_PROCESS.poll() is None


def spawn_local_service(
    data_root: Path,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    python_executable: str | None = None,
    popen: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    creationflags: int = 0,
) -> subprocess.Popen[str]:
    """Start the long-lived service without blocking the caller."""
    global _ACTIVE_PROCESS

    if not is_waitress_available():
        raise RuntimeError(waitress_unavailable_message())

    if is_service_running():
        raise RuntimeError(
            f"local ORM service already running (pid {_ACTIVE_PROCESS.pid})"
        )

    resolved = remember_data_root(data_root)
    if not resolved.is_dir():
        raise ValueError(f"data root must be an existing directory: {data_root}")

    command = build_launch_command(
        resolved,
        host=host,
        port=port,
        python_executable=python_executable,
    )
    _ACTIVE_PROCESS = popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )
    return _ACTIVE_PROCESS


def reset_launcher_state() -> None:
    """Clear session state (tests only)."""
    global _LAST_DATA_ROOT, _ACTIVE_PROCESS
    _LAST_DATA_ROOT = None
    _ACTIVE_PROCESS = None


def pick_data_root_with_dialog(
    *,
    parent: object | None = None,
    output_dir: Path | str | None = None,
    title: str = "ORM service data root",
) -> Path | None:
    """Show a directory dialog; return None if cancelled."""
    try:
        from PySide6.QtWidgets import QFileDialog
    except ImportError:
        return None

    initial = suggested_data_root(output_dir)
    start_dir = str(initial) if initial is not None else ""
    selected = QFileDialog.getExistingDirectory(parent, title, start_dir)
    if not selected:
        return None
    return Path(selected)


def start_local_service_interactive(
    *,
    parent: object | None = None,
    output_dir: Path | str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    status_cb: Callable[[str], None] | None = None,
) -> subprocess.Popen[str] | None:
    """Pick data root (dialog) and spawn; surface errors via ``status_cb`` or raise."""
    if not is_waitress_available():
        message = waitress_unavailable_message()
        if status_cb is not None:
            status_cb(message)
            return None
        raise RuntimeError(message)

    chosen = pick_data_root_with_dialog(parent=parent, output_dir=output_dir)
    if chosen is None:
        if status_cb is not None:
            status_cb("Start local ORM service cancelled.")
        return None

    try:
        process = spawn_local_service(chosen, host=host, port=port)
    except (OSError, RuntimeError, ValueError) as exc:
        if status_cb is not None:
            status_cb(f"Could not start local ORM service: {exc}")
            return None
        raise

    if status_cb is not None:
        status_cb(
            f"Local ORM service started at http://{host}:{port} "
            f"(pid {process.pid}, data-root {chosen})"
        )
    return process
