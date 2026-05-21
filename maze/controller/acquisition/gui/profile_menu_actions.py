"""File menu handlers for acquisition profile load/save/reload."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..profile import ProfileTaskMismatchError, gui_to_dict, load_profile, save_profile
from .identity import sanitize_session_id
from .profile_settings import (
    HAS_QT as HAS_QT_SETTINGS,
    save_last_profile_path,
    write_reload_last_profile,
)

if TYPE_CHECKING:
    from .main_window import MainWindow

try:
    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import QFileDialog, QMessageBox
except ImportError:
    QFileDialog = None  # type: ignore[misc, assignment]
    QMessageBox = None  # type: ignore[misc, assignment]

try:
    from PySide6.QtGui import QDesktopServices

    HAS_DESKTOP_SERVICES = True
except ImportError:
    HAS_DESKTOP_SERVICES = False


def _gui_dict_for_profile_save(window: MainWindow) -> dict[str, Any]:
    window._apply_ui_to_config()
    return gui_to_dict(
        track_show=window._config.track_show,
        track_async=window._config.track_async,
        track_enable_backup=window._config.track_enable_backup,
        track_enable_sleap=window._config.track_enable_sleap,
        track_sleap_path=window._config.sleap_model_path or "",
        track_confidence=window._config.sleap_confidence_pct,
        track_sleap_every_n=window._config.sleap_every_n,
        track_opacity=window._track_opacity.value(),
        display_brightness=window._display_brightness.value(),
        display_contrast=window._display_contrast.value(),
        camera_flip=window._camera_flip.isChecked(),
        camera_source=window._camera_source.currentText(),
        camera_device=window._camera_device.value(),
        arduino_port=(
            window._mc_port_combo.currentData() or window._mc_port_combo.currentText() or ""
        ).strip(),
    )


def _apply_profile_to_window(
    window: MainWindow,
    *,
    path: Path,
    session_id: str | None,
    trial_idx: int | None,
    gui: dict[str, Any] | None,
    slot: int | None,
) -> None:
    session_id_safe = sanitize_session_id(session_id) if session_id else ""
    window._profile_path = path
    window._apply_config_to_ui(gui=gui)
    dlg = getattr(window, "_settings_dialog", None)
    if dlg is not None and hasattr(dlg, "set_config"):
        dlg.set_config(window._config)
    window._trial_controller = window._task_spec.controller_factory(window._config)
    window._trial_controller.add_state_listener(window._on_trial_state_change)
    window._trial_controller.reset(session_id_safe, trial_idx, slot_idx=slot)
    if session_id_safe:
        window._session_id_edit.setText(session_id_safe)
    window._update_window_title()
    save_last_profile_path(window._profile_path, task_mode=window._task_mode)
    window._apply_status_and_buttons()


def on_load_profile(window: MainWindow) -> None:
    path, _ = QFileDialog.getOpenFileName(window, "Load profile", "", "JSON (*.json);;All (*)")
    if not path:
        return
    try:
        config, session_id, ti, gui, slot = load_profile(
            Path(path), expected_task_mode=window._task_mode
        )
        window._config = config
        _apply_profile_to_window(
            window, path=Path(path), session_id=session_id, trial_idx=ti, gui=gui, slot=slot
        )
        window.statusBar().showMessage(f"Loaded {path}")
    except ProfileTaskMismatchError as e:
        QMessageBox.warning(window, "Wrong task profile", str(e))
        window.statusBar().showMessage("Load cancelled: profile is for a different task.")
    except Exception as e:
        window.statusBar().showMessage(f"Load failed: {e}")


def on_save_profile(window: MainWindow) -> None:
    path = window._profile_path
    if not path:
        path_str, _ = QFileDialog.getSaveFileName(
            window, "Save profile", "", "JSON (*.json);;All (*)"
        )
        path = Path(path_str) if path_str else None
    if not path:
        return
    try:
        snapshot = window._trial_controller.get_session_snapshot()
        session_id, trial_idx, slot_idx = snapshot if snapshot else (None, None, None)
        gui = _gui_dict_for_profile_save(window)
        save_profile(
            window._config,
            path,
            session_id=session_id,
            trial_idx=trial_idx,
            slot_idx=slot_idx,
            gui=gui,
        )
        window._profile_path = path
        window._update_window_title()
        save_last_profile_path(window._profile_path, task_mode=window._task_mode)
        window.statusBar().showMessage(f"Saved {path}")
    except Exception as e:
        window.statusBar().showMessage(f"Save failed: {e}")


def on_save_profile_as(window: MainWindow) -> None:
    path, _ = QFileDialog.getSaveFileName(window, "Save profile as", "", "JSON (*.json);;All (*)")
    if not path:
        return
    try:
        snapshot = window._trial_controller.get_session_snapshot()
        session_id, trial_idx, slot_idx = snapshot if snapshot else (None, None, None)
        gui = _gui_dict_for_profile_save(window)
        save_profile(
            window._config,
            Path(path),
            session_id=session_id,
            trial_idx=trial_idx,
            slot_idx=slot_idx,
            gui=gui,
        )
        window._profile_path = Path(path)
        window._update_window_title()
        save_last_profile_path(window._profile_path, task_mode=window._task_mode)
        window.statusBar().showMessage(f"Saved {path}")
    except Exception as e:
        window.statusBar().showMessage(f"Save failed: {e}")


def on_open_profile_in_editor(window: MainWindow) -> None:
    if not window._profile_path or not window._profile_path.exists():
        window.statusBar().showMessage("Save profile first.")
        return
    if HAS_DESKTOP_SERVICES:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(window._profile_path)))
        window.statusBar().showMessage("Opened profile in editor.")
    else:
        window.statusBar().showMessage("Cannot open in editor (QDesktopServices unavailable).")


def on_reload_profile(window: MainWindow) -> None:
    if not window._profile_path or not window._profile_path.exists():
        window.statusBar().showMessage("No profile loaded.")
        return
    try:
        config, session_id, ti, gui, slot = load_profile(
            window._profile_path, expected_task_mode=window._task_mode
        )
        window._config = config
        _apply_profile_to_window(
            window,
            path=window._profile_path,
            session_id=session_id,
            trial_idx=ti,
            gui=gui,
            slot=slot,
        )
        window.statusBar().showMessage(f"Reloaded {window._profile_path}")
    except ProfileTaskMismatchError as e:
        QMessageBox.warning(window, "Wrong task profile", str(e))
        window.statusBar().showMessage("Reload skipped: profile is for a different task.")
    except Exception as e:
        window.statusBar().showMessage(f"Reload failed: {e}")


def on_toggle_reload_last_profile(window: MainWindow) -> None:
    if not HAS_QT_SETTINGS:
        return
    write_reload_last_profile(window._reload_last_profile_action.isChecked())
