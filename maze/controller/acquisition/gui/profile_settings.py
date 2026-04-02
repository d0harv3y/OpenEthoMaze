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


def save_last_profile_path(profile_path: Optional[Path]) -> None:
    if not HAS_QT or profile_path is None:
        return
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(KEY_LAST_PROFILE_PATH, str(profile_path))


def read_last_profile_path() -> Optional[Path]:
    if not HAS_QT:
        return None
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    path_str = settings.value(KEY_LAST_PROFILE_PATH, "", type=str)
    return Path(path_str) if path_str else None
