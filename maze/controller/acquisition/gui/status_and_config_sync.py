"""Status bar, run-button states, and config ↔ main-window widget sync."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.pose_status import read_pose_status_label

from .identity import sanitize_session_id

if TYPE_CHECKING:
    from .main_window import MainWindow

try:
    from ..arduino import HAS_SERIAL

    if HAS_SERIAL:
        import serial.tools.list_ports as _list_ports
    else:
        _list_ports = None
except ImportError:
    HAS_SERIAL = False
    _list_ports = None


def update_window_title(window: MainWindow) -> None:
    prefix = f"{window._task_spec.window_title} ({window._task_spec.display_name})"
    if window._profile_path:
        window.setWindowTitle(f"{prefix} — {window._profile_path}")
    else:
        window.setWindowTitle(f"{prefix} — Unsaved")


def apply_status_and_buttons(window: MainWindow) -> None:
    """Apply trial controller status dict and button states to widgets. See docs/button_flow_state.md."""
    x, y = window._last_track_xy if window._last_track_xy else (0.0, 0.0)
    d = window._trial_controller.get_status_dict(x, y)
    window._status_state.setText(str(d["state"]))
    window._status_trial.setText(str(d["trial"]))
    window._status_exit.setText(str(d["exit"]))
    window._status_animal_id.setText(str(d["animal_id"]))
    window._status_iti.setText(str(d["iti"]))
    window._status_trial_timer.setText(str(d["trial_timer"]))
    window._status_duty.setText(str(d["duty"]))
    if d.get("session_id", "") != window._session_id_edit.text().strip():
        window._session_id_edit.setText(sanitize_session_id(str(d.get("session_id", ""))))
    bs = window._trial_controller.get_button_states()
    video_ok = window._is_video_available()
    mc_ok = window._is_mc_connected()
    virtual_mode = video_ok and window._camera_source.currentText().startswith("Virtual")
    device_ready = (mc_ok or virtual_mode) if window._task_spec.requires_mc_connection else True
    run_ok = window._dev_mode or (video_ok and device_ready)
    window._start_trial_btn.setEnabled(bs["start"] and run_ok)
    window._previous_trial_btn.setEnabled(bs["previous"] and run_ok)
    window._next_trial_btn.setEnabled(bs["next"] and run_ok)
    window._end_trial_btn.setEnabled(bs["end_trial"] and run_ok)
    window._stop_btn.setEnabled(bs["stop"] and run_ok)
    window._camera_flip.setEnabled(not window._trial_controller.run_active)
    sync_pose_status_label(window)
    sync_settings_apply_enabled(window)


def sync_pose_status_label(window: MainWindow) -> None:
    """Update Pose status from the current trial group in the results H5."""
    label = getattr(window, "_status_pose", None)
    if label is None:
        return
    # Post-trial ``process_trial`` opens the same H5 for append on a worker thread; a
    # concurrent read-only open from the GUI camera loop fails on Windows HDF5.
    if getattr(window, "_analysis_worker", None) is not None:
        return

    output_dir = (window._config.output_dir or "").strip()
    if not output_dir:
        label.setText("—")
        return

    h5_name = (window._config.h5_filename or "trials.h5").strip() or "trials.h5"
    db_path = Path(output_dir) / h5_name
    if not db_path.is_file():
        label.setText("—")
        return

    x, y = window._last_track_xy if window._last_track_xy else (0.0, 0.0)
    status = window._trial_controller.get_status_dict(x, y)
    animal_id = str(status.get("animal_id", "")).strip()
    session_id = str(status.get("session_id", "")).strip()
    trial = str(status.get("trial", "")).strip()
    if not animal_id or animal_id == "—" or not session_id or not trial or trial == "—":
        label.setText("—")
        return

    key = TrialKey(animal_id=animal_id, session=session_id, trial=trial)
    text = read_pose_status_label(db_path, key)
    label.setText(text.removeprefix("Pose: ").strip() or "—")


def sync_settings_apply_enabled(window: MainWindow) -> None:
    tc = window._trial_controller
    allow = not tc.is_trial_running_phase()
    dlg = getattr(window, "_settings_dialog", None)
    if dlg is not None and hasattr(dlg, "set_apply_enabled"):
        dlg.set_apply_enabled(allow)


def apply_config_to_ui(window: MainWindow, gui: Optional[dict] = None) -> None:
    if window._tracking_controller is not None:
        window._tracking_controller.set_config(window._config)
    phase_value = window._task_spec.get_phase_value(window._config)
    if window._task_spec.phase_options:
        idx = window._phase_combo.findData(phase_value)
        if idx >= 0:
            window._phase_combo.setCurrentIndex(idx)
        else:
            window._phase_combo.setCurrentIndex(0)
    mode_value = window._task_spec.get_mode_value(window._config)
    idx = window._mode_combo.findData(mode_value)
    if idx >= 0:
        window._mode_combo.setCurrentIndex(idx)
    else:
        window._mode_combo.setCurrentIndex(0)
    out = window._config.output_dir
    window._output_dir_edit.setText(out or "")
    window._h5_filename_edit.setText(window._config.h5_filename or "trials.h5")
    op = max(0, min(100, window._config.overlay_opacity_pct))
    window._track_opacity.setValue(op)
    window._track_opacity_label.setText(f"{op}%")
    window._run_analysis_after_trial_cb.setChecked(window._config.run_analysis_after_trial)
    if gui:
        apply_gui_dict_to_ui(window, gui)
    a_dlg = getattr(window, "_analysis_settings_dialog", None)
    if a_dlg is not None and hasattr(a_dlg, "set_params"):
        a_dlg.set_params(
            window._config.analysis_trajectory,
            window._config.analysis_trace_quality,
        )
    if (
        window._camera_timer is not None
        and window._camera_timer.isActive()
        and window._camera_controller is not None
    ):
        window._camera_timer.setInterval(
            window._camera_controller.preview_timer_interval_ms(window._config)
        )
    window._invalidate_tracker_cache()
    apply_status_and_buttons(window)


def apply_gui_dict_to_ui(window: MainWindow, gui: dict) -> None:
    """Restore GUI-only controls from a profile gui dict (and merge into config for tracking)."""
    if gui.get("track_show") is not None:
        window._config.track_show = bool(gui["track_show"])
    if gui.get("track_async") is not None:
        window._config.track_async = bool(gui["track_async"])
    if gui.get("track_enable_backup") is not None:
        window._config.track_enable_backup = bool(gui["track_enable_backup"])
    if gui.get("track_enable_sleap") is not None:
        window._config.track_enable_sleap = bool(gui["track_enable_sleap"])
    elif gui.get("track_backup_only") is not None:
        window._config.track_enable_backup = True
        window._config.track_enable_sleap = not bool(gui["track_backup_only"])
    if "track_sleap_path" in gui:
        window._config.sleap_model_path = str(gui.get("track_sleap_path") or "").strip()
    if gui.get("track_confidence") is not None:
        window._config.sleap_confidence_pct = max(0, min(100, int(gui["track_confidence"])))
    if gui.get("track_sleap_every_n") is not None:
        window._config.sleap_every_n = max(1, min(5, int(gui["track_sleap_every_n"])))
    if gui.get("track_opacity") is not None:
        v = max(0, min(100, int(gui["track_opacity"])))
        window._config.overlay_opacity_pct = v
        window._track_opacity.setValue(v)
        window._track_opacity_label.setText(f"{v}%")
    if gui.get("display_brightness") is not None:
        window._display_brightness.setValue(int(gui["display_brightness"]))
        window._display_brightness_label.setText(str(gui["display_brightness"]))
    if gui.get("display_contrast") is not None:
        v = max(50, min(200, int(gui["display_contrast"])))
        window._display_contrast.setValue(v)
        window._display_contrast_label.setText(f"{v}%")
    if gui.get("camera_flip") is not None:
        window._camera_flip.setChecked(bool(gui["camera_flip"]))
    if gui.get("camera_source") is not None:
        idx = window._camera_source.findText(str(gui["camera_source"]))
        if idx >= 0:
            window._camera_source.setCurrentIndex(idx)
    if gui.get("camera_device") is not None:
        window._camera_device.setValue(max(0, min(15, int(gui["camera_device"]))))
    if gui.get("arduino_port") is not None:
        port = str(gui["arduino_port"]).strip()
        if port and HAS_SERIAL and _list_ports is not None:
            idx = window._mc_port_combo.findData(port)
            if idx >= 0:
                window._mc_port_combo.setCurrentIndex(idx)
            else:
                window._mc_port_combo.addItem(port, port)
                window._mc_port_combo.setCurrentIndex(window._mc_port_combo.count() - 1)


def apply_ui_to_config(window: MainWindow) -> None:
    p = window._phase_combo.currentData()
    if p is not None and window._task_spec.set_phase_value is not None:
        window._task_spec.set_phase_value(window._config, str(p))
    m = window._mode_combo.currentData()
    if m is not None:
        window._task_spec.set_mode_value(window._config, str(m))
    raw = window._output_dir_edit.text().strip()
    window._config.output_dir = raw if raw else None
    h5_raw = window._h5_filename_edit.text().strip()
    window._config.h5_filename = h5_raw if h5_raw else "trials.h5"
    window._config.overlay_opacity_pct = max(0, min(100, window._track_opacity.value()))
    window._config.run_analysis_after_trial = window._run_analysis_after_trial_cb.isChecked()
