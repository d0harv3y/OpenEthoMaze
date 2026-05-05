from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from PySide6.QtCore import QSettings

    HAS_QT = True
except ImportError:
    HAS_QT = False
    QSettings = None  # type: ignore[assignment]


SETTINGS_ORG = "Maze"
SETTINGS_APP = "Acquisition"
KEY_RELOAD_LAST_PROFILE = "reload_last_profile"
KEY_LAST_PROFILE_PATH = "last_profile_path"
KEY_LAST_PROFILE_PATH_VAST = "last_profile_path_vast"
KEY_LAST_PROFILE_PATH_RAM = "last_profile_path_ram"
KEY_LAST_ANALYSIS_PROFILE_PATH = "last_analysis_profile_path"


def read_reload_last_profile() -> bool:
    if not HAS_QT:
        return True
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return settings.value(KEY_RELOAD_LAST_PROFILE, True, type=bool)


def write_reload_last_profile(enabled: bool) -> None:
    if not HAS_QT:
        return
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(KEY_RELOAD_LAST_PROFILE, bool(enabled))


def save_last_profile_path(
    profile_path: Optional[Path], *, task_mode: str = "vast"
) -> None:
    """Persist last profile path for the given task (``vast`` or ``ram``).

    Also updates the legacy global key so older builds still see a last path.
    """
    if not HAS_QT or profile_path is None:
        return
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    mode = str(task_mode).strip().lower()
    key = KEY_LAST_PROFILE_PATH_RAM if mode == "ram" else KEY_LAST_PROFILE_PATH_VAST
    settings.setValue(key, str(profile_path))
    settings.setValue(KEY_LAST_PROFILE_PATH, str(profile_path))


def read_last_profile_path(*, task_mode: str = "vast") -> Optional[Path]:
    """Return the last profile path for this task, never a path for the other task.

    Falls back to the legacy single key only when its JSON matches ``task_mode``.
    """
    if not HAS_QT:
        return None
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    mode = str(task_mode).strip().lower()
    key = KEY_LAST_PROFILE_PATH_RAM if mode == "ram" else KEY_LAST_PROFILE_PATH_VAST
    path_str = settings.value(key, "", type=str)
    if path_str:
        return Path(path_str)
    legacy = settings.value(KEY_LAST_PROFILE_PATH, "", type=str)
    if not legacy:
        return None
    try:
        from maze.controller.acquisition.profile import read_profile_task_mode

        p = Path(legacy)
        if p.is_file() and read_profile_task_mode(p) == mode:
            return p
    except Exception:
        return None
    return None


def save_last_analysis_profile_path(profile_path: Optional[Path]) -> None:
    if not HAS_QT or profile_path is None:
        return
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(KEY_LAST_ANALYSIS_PROFILE_PATH, str(profile_path))


def read_last_analysis_profile_path() -> Optional[Path]:
    if not HAS_QT:
        return None
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    path_str = settings.value(KEY_LAST_ANALYSIS_PROFILE_PATH, "", type=str)
    if not path_str:
        return None
    return Path(path_str)
