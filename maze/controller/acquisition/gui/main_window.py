"""
Main controller GUI: profile, calibration, config, run, export.

"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..profile import ProfileTaskMismatchError, load_profile
from ..playback_loader import PlaybackHydration
from ..recording import TrialRecorder
from .. import app_logging
from ..task_registry import AcquisitionMode, get_task_spec
from .analysis_worker import AnalysisWorker
from .file_actions import (
    launch_h5web_for_path,
)
from .identity import sanitize_session_id
from .pipeline_menu_actions import (
    on_pipeline_analyze,
    on_pipeline_discovery,
    on_pipeline_inference,
    on_pipeline_kpms_apply,
    on_pipeline_kpms_fit,
    on_pipeline_qc_summary,
    on_pipeline_render_overlay,
    on_run_exports,
)
from .preview_events import filter_camera_preview_events
from .camera_loop import (
    invalidate_tracker_cache,
    is_video_available,
    on_camera_tick,
    on_start_camera,
    on_stop_camera,
    on_virtual_scrub_changed,
    reset_sleap_node_jump_state,
    update_pose_last_and_valid,
    virtual_timing_frames_label,
)
from .trial_run_actions import (
    compute_trial_clock_virtual_dt_s,
    on_next_trial,
    on_previous_trial,
    on_run_timer,
    on_session_controls_changed,
    on_start_trial,
    on_stop_run,
    on_trial_state_change,
    stop_trial_recorder_if_active,
    virtual_trial_clock_enabled,
)
from .window_layout import build_main_window_layout
from .status_and_config_sync import (
    apply_config_to_ui,
    apply_status_and_buttons,
    apply_ui_to_config,
    sync_settings_apply_enabled,
    update_window_title,
)
from .profile_menu_actions import (
    on_load_profile,
    on_open_profile_in_editor,
    on_reload_profile,
    on_save_profile,
    on_save_profile_as,
    on_toggle_reload_last_profile,
)
from .mc_actions import flash_firmware, refresh_serial_ports, toggle_mc_connection
from .menus import build_main_window_menus
from .pose_jump_state import PoseJumpState
from .profile_settings import (
    HAS_QT as HAS_QT_SETTINGS,
    read_last_profile_path,
    read_reload_last_profile,
    save_last_profile_path,
)

QT_ERROR_MESSAGE = "PySide6 is required for the GUI. Install with: pip install PySide6"
DEFAULT_WINDOW_SIZE = (500, 400)


try:
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
    )
    from PySide6.QtCore import QTimer, QUrl

    HAS_QT = True
except ImportError:
    HAS_QT = False

try:
    from PySide6.QtGui import QDesktopServices

    HAS_DESKTOP_SERVICES = True
except ImportError:
    HAS_DESKTOP_SERVICES = False

# Camera: optional OpenCV and/or Vimba (GigE) for live preview
try:
    import cv2 as _cv2
    from ..camera import (
        HAS_CAMERA,
        HAS_VIMBA,
        CameraController,
    )
except (ImportError, RuntimeError):
    _cv2 = None
    HAS_CAMERA = False
    HAS_VIMBA = False

# Tracking: backup (adaptive threshold) and optional SLEAP
try:
    from ..tracking import AdaptiveThresholdTracker, HybridTracker, TrackingController

    HAS_TRACKING = True
except ImportError:
    AdaptiveThresholdTracker = None
    HybridTracker = None
    TrackingController = None
    HAS_TRACKING = False

# MC (Arduino) serial for vibration stimulus
try:
    from ..arduino import ArduinoStimulus, HAS_SERIAL

    if HAS_SERIAL:
        import serial.tools.list_ports as _list_ports
    else:
        _list_ports = None
except ImportError:
    ArduinoStimulus = None  # type: ignore[misc, assignment]
    HAS_SERIAL = False
    _list_ports = None

# Settings dialog and section widget
try:
    from .settings_dialog import SettingsDialog
    from .section_with_settings import SectionWithSettings

    HAS_SETTINGS_DIALOG = True
except ImportError:
    SettingsDialog = None
    SectionWithSettings = None
    HAS_SETTINGS_DIALOG = False

try:
    from .analysis_settings_dialog import AnalysisSettingsDialog

    HAS_ANALYSIS_SETTINGS_DIALOG = True
except ImportError:
    AnalysisSettingsDialog = None
    HAS_ANALYSIS_SETTINGS_DIALOG = False

try:
    from .kpms_fit_dialog import HAS_KPMS_FIT_DIALOG
except ImportError:
    HAS_KPMS_FIT_DIALOG = False

try:
    from .kpms_apply_dialog import HAS_KPMS_APPLY_DIALOG
except ImportError:
    HAS_KPMS_APPLY_DIALOG = False

try:
    from .qc_summary_dialog import HAS_QC_SUMMARY_DIALOG
except ImportError:
    HAS_QC_SUMMARY_DIALOG = False

try:
    from .overlay_dialog import HAS_OVERLAY_DIALOG
except ImportError:
    HAS_OVERLAY_DIALOG = False

try:
    from .pipeline_dialogs import HAS_PIPELINE_DIALOGS
except ImportError:
    HAS_PIPELINE_DIALOGS = False


class MainWindow(QMainWindow):
    """Main window: profile, calibration, run, export."""

    def __init__(self, task_mode: AcquisitionMode = "vast", dev: bool = False) -> None:
        super().__init__()
        self._task_mode = task_mode
        self._task_spec = get_task_spec(task_mode)
        self._dev_mode = dev
        self._config = self._task_spec.config_factory()
        self._profile_path: Optional[Path] = None
        self._db_path: Optional[Path] = None
        self._update_window_title()
        self._camera_timer: Optional[QTimer] = None
        self._last_preview_img_size: Optional[Tuple[int, int]] = (
            None  # (width, height) for click mapping
        )
        # Last flipped raw frame (BGR or gray) for eyedropper hover; updated each camera tick.
        self._last_eyedropper_frame_bgr: Optional[np.ndarray] = None
        self._last_track_xy: Optional[Tuple[float, float]] = (
            None  # latest valid tracking position for run loop
        )
        self._pose_jump_state = PoseJumpState()
        self._tracking_controller = (
            TrackingController(self._config)
            if HAS_TRACKING and TrackingController is not None
            else None
        )
        self._camera_controller = CameraController(self._config) if HAS_CAMERA else None
        self._display_fps_times: list = []  # ring of frame timestamps for display FPS (max 30)
        self._display_fps_max_samples = 30
        self._last_display_fps: float = 0.0  # latest preview FPS estimate for dev HUD
        # Per-phase process times (ms) for last camera frame; see Display FPS tooltip.
        self._last_frame_phase_ms: Dict[str, float] = {}
        # Virtual acquisition: during idle (before Start trial), pause video frame advancement
        # so playback starts exactly when Start trial is pressed.
        self._virtual_video_path: Optional[Path] = None
        self._playback_hydration: Optional[PlaybackHydration] = None
        self._virtual_has_initial_frame: bool = False
        self._virtual_cached_frame_raw: Optional[np.ndarray] = None
        # Cached frame index from CameraController during the paused preview.
        self._virtual_cached_frame_index: Optional[int] = None
        # Virtual playback: previous OpenCV frame index while advancing (detect loop / seek-back).
        self._last_virtual_playback_frame_idx: Optional[int] = None
        # Per-node consecutive frames beyond node_max_jump_px (same length as nodes); SLEAP overlay only.
        # Last overlay track_source ("sleap" / "fallback") to detect pipeline switches.
        self._last_overlay_track_source: Optional[str] = None
        # Prior **Flip image** checkbox state; toggling resets pose jump memory (coordinate mirror).
        self._last_preview_flip_checked: Optional[bool] = None
        self._gui_error_log: list = []  # list of timestamped error lines for View error log
        self._last_sleap_device_logged: Optional[str] = None
        self._last_sleap_log_time_s: Optional[float] = None
        self._trial_controller = self._task_spec.controller_factory(self._config)
        self._trial_controller.add_state_listener(self._on_trial_state_change)
        self._arduino_stimulus: Optional["ArduinoStimulus"] = None
        self._trial_recorder: Optional[TrialRecorder] = None
        self._record_frame_index: int = 0
        self._run_timer: Optional[QTimer] = None
        self._run_timer_interval_ms = 100
        self._run_timer_last_s: Optional[float] = None
        # Virtual duration override: trial elapsed tracks video frame time (see _compute_trial_clock_virtual_dt_s).
        self._prev_trial_running_virtual_clock: bool = False
        self._virtual_trial_clock_last_fi: Optional[int] = None
        self._analysis_worker: Optional["AnalysisWorker"] = None
        self._analysis_settings_dialog = None
        build_main_window_layout(self)
        self._build_menus()
        if not HAS_CAMERA:
            self._camera_start_btn.setEnabled(False)
            self._camera_label.setText("Camera unavailable (install opencv-python)")
        if not HAS_TRACKING:
            pass  # Tracking options are in Settings → Tracking
        self.statusBar().showMessage("Ready. Load a profile or configure session.")
        self._apply_startup_profile()

    def _update_window_title(self) -> None:
        update_window_title(self)

    def _on_track_opacity_changed(self, value: int) -> None:
        self._track_opacity_label.setText(f"{value}%")

    def _reset_sleap_node_jump_state(self) -> None:
        reset_sleap_node_jump_state(self)

    def _invalidate_tracker_cache(self) -> None:
        invalidate_tracker_cache(self)

    def _update_pose_last_and_valid(
        self,
        pose_xy: Optional[np.ndarray],
        node_max_jump_px: float,
        node_jump_confirm_frames: int,
    ) -> Optional[np.ndarray]:
        return update_pose_last_and_valid(
            self, pose_xy, node_max_jump_px, node_jump_confirm_frames
        )

    def _on_display_brightness_changed(self, value: int) -> None:
        self._display_brightness_label.setText(str(value))

    def _on_display_contrast_changed(self, value: int) -> None:
        self._display_contrast_label.setText(f"{value}%")

    def _on_browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Output folder")
        if path:
            self._output_dir_edit.setText(path)
            self._config.output_dir = path

    def _build_menus(self) -> None:
        build_main_window_menus(
            self,
            reload_last_profile_checked=read_reload_last_profile(),
            pipeline_dialogs_available=HAS_PIPELINE_DIALOGS,
            kpms_fit_dialog_available=HAS_KPMS_FIT_DIALOG,
            kpms_apply_dialog_available=HAS_KPMS_APPLY_DIALOG,
            qc_summary_dialog_available=HAS_QC_SUMMARY_DIALOG,
            overlay_dialog_available=HAS_OVERLAY_DIALOG,
        )

    def _on_save_profile_as(self) -> None:
        on_save_profile_as(self)

    def _on_open_profile_in_editor(self) -> None:
        on_open_profile_in_editor(self)

    def _on_reload_profile(self) -> None:
        on_reload_profile(self)

    def _on_file_exit(self) -> None:
        if self._run_timer is not None and self._run_timer.isActive():
            r = QMessageBox.question(
                self,
                "Exit",
                "Session in progress. Stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self.close()

    _SETTINGS_TAB_NAMES_VAST = ("Tracking", "Task", "Session", "Animals", "Trial schedule")
    _SETTINGS_TAB_NAMES_RAM = ("Tracking", "Task", "Session", "Animals", "Trial schedule")

    def _on_settings(self) -> None:
        if not HAS_SETTINGS_DIALOG or SettingsDialog is None:
            self.statusBar().showMessage("Settings dialog unavailable.")
            return
        dlg = getattr(self, "_settings_dialog", None)
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            self._sync_settings_apply_enabled()
            return
        dlg = SettingsDialog(
            self._config,
            self,
            task_mode=self._task_mode,
            initial_tab_index=None,
        )
        self._settings_dialog = dlg
        dlg.accepted.connect(lambda: self.statusBar().showMessage("Settings applied."))
        dlg.show()
        dlg.raise_()
        self._sync_settings_apply_enabled()

    def _on_analysis_settings(self) -> None:
        if not HAS_ANALYSIS_SETTINGS_DIALOG or AnalysisSettingsDialog is None:
            self.statusBar().showMessage("Analysis settings dialog unavailable.")
            return
        dlg = getattr(self, "_analysis_settings_dialog", None)
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            return
        dlg = AnalysisSettingsDialog(
            self._config.analysis_trajectory,
            self._config.analysis_trace_quality,
            self,
            on_apply=self._apply_analysis_config,
        )
        self._analysis_settings_dialog = dlg
        dlg.show()
        dlg.raise_()

    def _apply_analysis_config(self, traj, trace_quality) -> None:
        self._config.analysis_trajectory = traj
        self._config.analysis_trace_quality = trace_quality
        self.statusBar().showMessage("Applied analysis settings.")

    def _on_pipeline_discovery(self) -> None:
        on_pipeline_discovery(self)

    def _on_pipeline_inference(self) -> None:
        on_pipeline_inference(self)

    def _on_pipeline_analyze(self) -> None:
        on_pipeline_analyze(self)

    def _on_pipeline_kpms_fit(self) -> None:
        on_pipeline_kpms_fit(self)

    def _on_pipeline_kpms_apply(self) -> None:
        on_pipeline_kpms_apply(self)

    def _on_pipeline_qc_summary(self) -> None:
        on_pipeline_qc_summary(self)

    def _on_pipeline_render_overlay(self) -> None:
        on_pipeline_render_overlay(self)

    def _on_open_settings_to_tab(self, tab_name: str | int) -> None:
        if not HAS_SETTINGS_DIALOG or SettingsDialog is None:
            self.statusBar().showMessage("Settings dialog unavailable.")
            return
        if isinstance(tab_name, str):
            normalized = tab_name.strip().lower()
            if self._task_mode == "vast":
                tab_index = {
                    "tracking": 0,
                    "task": 1,
                    "session": 2,
                    "animals": 3,
                    "trial_schedule": 4,
                    "trial schedule": 4,
                }.get(normalized, 0)
            else:
                tab_index = {
                    "tracking": 0,
                    "task": 1,
                    "session": 2,
                    "animals": 3,
                    "trial_schedule": 4,
                    "trial schedule": 4,
                }.get(normalized, 0)
        else:
            tab_index = int(tab_name)
        dlg = getattr(self, "_settings_dialog", None)
        if dlg is None:
            dlg = SettingsDialog(
                self._config,
                self,
                task_mode=self._task_mode,
                initial_tab_index=tab_index,
            )
            self._settings_dialog = dlg
            dlg.accepted.connect(
                lambda: (
                    self._apply_config_to_ui(),
                    self.statusBar().showMessage("Settings applied."),
                )
            )
        else:
            dlg.set_current_tab(tab_index)
        names = (
            self._SETTINGS_TAB_NAMES_VAST
            if self._task_mode == "vast"
            else self._SETTINGS_TAB_NAMES_RAM
        )
        tab_name = names[tab_index] if 0 <= tab_index < len(names) else "Settings"
        self.statusBar().showMessage(f"Settings → {tab_name}")
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        self._sync_settings_apply_enabled()

    def _on_analysis_finished(self, success: bool, message: str) -> None:
        # Join before dropping the last ref — otherwise QThread can be destroyed
        # while C++/Python is still unwinding the worker, which crashes (stderr:
        # "QThread: Destroyed while thread is still running"), often after modal
        # dialogs e.g. trial overwrite.
        w = self._analysis_worker
        self._analysis_worker = None
        if w is not None:
            w.wait()
        self.statusBar().showMessage(
            message if message else ("Analysis done" if success else "Analysis failed")
        )

    def _on_end_trial(self) -> None:
        msg = self._trial_controller.do_end_trial()
        self._apply_status_and_buttons()
        self.statusBar().showMessage(msg)

    def eventFilter(self, obj, event) -> bool:
        filter_camera_preview_events(self, obj, event)
        return super().eventFilter(obj, event)

    def _on_virtual_scrub_changed(self, value: int) -> None:
        on_virtual_scrub_changed(self, value)

    def _on_camera_tick(self) -> None:
        on_camera_tick(self)

    def _on_start_camera(self) -> None:
        on_start_camera(self)

    def _on_stop_camera(self) -> None:
        on_stop_camera(self)

    def _on_mc_refresh_ports(self) -> None:
        """Repopulate COM port combo from serial.tools.list_ports."""
        refresh_serial_ports(self._mc_port_combo, _list_ports)

    def _on_mc_connect(self) -> None:
        """Toggle MC connection: connect if disconnected, disconnect if connected."""
        if ArduinoStimulus is None:
            self.statusBar().showMessage("MC serial support unavailable.")
            return
        try:
            result = toggle_mc_connection(
                current_stimulus=self._arduino_stimulus,
                arduino_cls=ArduinoStimulus,
                port_combo=self._mc_port_combo,
                stimulus_config=self._config.stimulus,
                config=self._config,
            )
            self._arduino_stimulus = result.stimulus
            self._mc_connect_btn.setText(result.button_text)
            self._mc_status_label.setText(result.status_label)
            self._mc_status_label.setStyleSheet(result.status_style)
            self.statusBar().showMessage(result.status_message)
            self._apply_status_and_buttons()
        except Exception as e:
            self._arduino_stimulus = None
            self.statusBar().showMessage(f"MC connect failed: {e}")

    def _on_mc_flash(self) -> None:
        """Compile and upload firmware via arduino-cli (dev only)."""
        flash_firmware(
            parent=self,
            dev_mode=self._dev_mode,
            port_combo=self._mc_port_combo,
            status_cb=self.statusBar().showMessage,
        )

    def closeEvent(self, event) -> None:
        if self._run_timer is not None and self._run_timer.isActive():
            r = QMessageBox.question(
                self,
                "Exit",
                "Session in progress. Stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._on_stop_run()
        if self._arduino_stimulus is not None:
            self._arduino_stimulus.disconnect()
            self._mc_connect_btn.setText("Connect")
            self._mc_status_label.setText("Disconnected")
            self._mc_status_label.setStyleSheet("color: gray;")
        self._on_stop_camera()
        w = self._analysis_worker
        if w is not None and w.isRunning():
            # Avoid destroying MainWindow while AnalysisWorker QThread is still running.
            w.wait(300_000)
        self._analysis_worker = None
        super().closeEvent(event)

    def _is_video_available(self) -> bool:
        return is_video_available(self)

    def _is_mc_connected(self) -> bool:
        """True if MC (Arduino) is connected and correct firmware is running."""
        return bool(self._arduino_stimulus is not None and self._arduino_stimulus.connected)

    @staticmethod
    def _virtual_timing_frames_label(timing: Dict[str, Any]) -> str:
        return virtual_timing_frames_label(timing)

    def _apply_status_and_buttons(self) -> None:
        apply_status_and_buttons(self)

    def _sync_settings_apply_enabled(self) -> None:
        sync_settings_apply_enabled(self)

    def _virtual_trial_clock_enabled(self) -> bool:
        return virtual_trial_clock_enabled(self)

    def _compute_trial_clock_virtual_dt_s(
        self, running: bool, prev_running: bool
    ) -> Optional[float]:
        return compute_trial_clock_virtual_dt_s(self, running, prev_running)

    def _on_run_timer(self) -> None:
        on_run_timer(self)

    def _on_stop_run(self) -> None:
        on_stop_run(self)

    def _on_trial_state_change(self, new_state) -> None:
        on_trial_state_change(self, new_state)

    def _stop_trial_recorder_if_active(self) -> None:
        stop_trial_recorder_if_active(self)

    def _on_start_trial(self) -> None:
        on_start_trial(self)

    def _on_previous_trial(self) -> None:
        on_previous_trial(self)

    def _on_next_trial(self) -> None:
        on_next_trial(self)

    def _on_session_controls_changed(self) -> None:
        on_session_controls_changed(self)

    def _apply_config_to_ui(self, gui: Optional[dict] = None) -> None:
        apply_config_to_ui(self, gui=gui)

    def _apply_ui_to_config(self) -> None:
        apply_ui_to_config(self)

    def _read_reload_last_profile(self) -> bool:
        return read_reload_last_profile()

    def _save_last_profile_path(self) -> None:
        save_last_profile_path(self._profile_path, task_mode=self._task_mode)

    def _on_toggle_reload_last_profile(self) -> None:
        on_toggle_reload_last_profile(self)

    def _gui_log_error(self, message: str) -> None:
        """Append a message to the GUI error log (View error log) and to the rotating file log."""

        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        self._gui_error_log.append(line)
        if len(self._gui_error_log) > 1000:
            self._gui_error_log = self._gui_error_log[-1000:]
        app_logging.log_error(message)

    def _set_sleap_status_failed(self, err: Optional[str]) -> None:
        """Log SLEAP load failure to error log (status no longer shown on main UI)."""
        err_str = (str(err).strip() if err is not None else "") or "Unknown error"
        self._gui_log_error("SLEAP: " + err_str)

    def _on_view_error_log(self) -> None:
        """Open a dialog showing the GUI error log and link to the rotating file log."""
        if not HAS_QT:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Error log")
        layout = QVBoxLayout(dialog)
        log_path = app_logging.get_current_log_path()
        if log_path is not None:
            path_label = QLabel(f"Log file (this run): {log_path}")
            path_label.setWordWrap(True)
            path_label.setStyleSheet("color: gray; font-size: 11px;")
            layout.addWidget(path_label)
        te = QPlainTextEdit()
        te.setReadOnly(True)
        te.setMinimumSize(500, 300)
        lines = self._gui_error_log[-500:] if self._gui_error_log else ["No errors logged."]
        te.setPlainText("\n".join(lines))
        layout.addWidget(te)
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy")

        def copy_log():
            cb = QApplication.clipboard()
            if cb:
                cb.setText(te.toPlainText())

        copy_btn.clicked.connect(copy_log)
        clear_btn = QPushButton("Clear")

        def clear_log():
            self._gui_error_log.clear()
            te.setPlainText("No errors logged.")

        clear_btn.clicked.connect(clear_log)
        if log_path is not None and HAS_DESKTOP_SERVICES:
            open_folder_btn = QPushButton("Open log folder")

            def open_folder():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_logging.get_log_dir())))

            open_folder_btn.clicked.connect(open_folder)
            btn_layout.addWidget(open_folder_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        dialog.exec()

    def _on_open_log_folder(self) -> None:
        """Open the log folder in the system file manager."""
        if HAS_DESKTOP_SERVICES:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_logging.get_log_dir())))
        else:
            self.statusBar().showMessage("Cannot open folder (QDesktopServices not available)")

    def _apply_startup_profile(self) -> None:
        """On startup: optionally load last profile and restore position; else ensure state machine at (0,0)."""
        if not read_reload_last_profile():
            self._trial_controller.ensure_created(self._session_id_edit.text().strip(), 0)
            self._apply_status_and_buttons()
            return
        if not HAS_QT_SETTINGS:
            self._trial_controller.ensure_created(self._session_id_edit.text().strip(), 0)
            self._apply_status_and_buttons()
            return
        path = read_last_profile_path(task_mode=self._task_mode)
        if path and path.exists():
            try:
                self._config, session_id, ti, gui, slot = load_profile(
                    path, expected_task_mode=self._task_mode
                )
                session_id_safe = sanitize_session_id(session_id) if session_id else ""
                self._profile_path = path
                self._apply_config_to_ui(gui=gui)
                self._trial_controller = self._task_spec.controller_factory(self._config)
                self._trial_controller.add_state_listener(self._on_trial_state_change)
                self._trial_controller.reset(session_id_safe, ti, slot_idx=slot)
                if session_id_safe:
                    self._session_id_edit.setText(session_id_safe)
                self._update_window_title()
                self._apply_status_and_buttons()
                self.statusBar().showMessage(f"Loaded last profile: {path}")
            except ProfileTaskMismatchError:
                self._trial_controller.ensure_created(self._session_id_edit.text().strip(), 0)
                self._apply_status_and_buttons()
                self.statusBar().showMessage(
                    "Last profile is for a different task; skipped auto-load."
                )
            except Exception:
                self._trial_controller.ensure_created(self._session_id_edit.text().strip(), 0)
                self._apply_status_and_buttons()
        else:
            self._trial_controller.ensure_created(self._session_id_edit.text().strip(), 0)
            self._apply_status_and_buttons()

    def _on_load_profile(self) -> None:
        on_load_profile(self)

    def _on_save_profile(self) -> None:
        on_save_profile(self)

    def _on_stop(self) -> None:
        self._on_stop_run()
        self.statusBar().showMessage("Stopped.")

    def _on_run_exports(self) -> None:
        on_run_exports(self)

    def _on_open_current_db_h5web(self) -> None:
        """Open the current output H5 DB (output_dir + h5_filename) in h5web."""
        output_dir = self._config.output_dir
        if not output_dir:
            self.statusBar().showMessage("No output folder set.")
            return
        h5_name = (self._config.h5_filename or "trials.h5").strip() or "trials.h5"
        if Path(h5_name).name != h5_name:
            h5_name = Path(h5_name).name
        db_path = Path(output_dir) / h5_name
        launch_h5web_for_path(db_path, self.statusBar().showMessage)

    def _on_open_h5web(self) -> None:
        """Open a user-selected H5 file in h5web."""
        h5_path_str, _ = QFileDialog.getOpenFileName(
            self, "Select H5 file", "", "HDF5 (*.h5 *.hdf5);;All (*)"
        )
        if not h5_path_str:
            return
        launch_h5web_for_path(Path(h5_path_str), self.statusBar().showMessage)

    def _on_start_local_service(self) -> None:
        """Spawn long-lived maze-local-service (subprocess; does not block Qt)."""
        from maze.controller.local_service_launcher import start_local_service_interactive

        output_dir = Path(self._config.output_dir) if self._config.output_dir else None
        start_local_service_interactive(
            parent=self,
            output_dir=output_dir,
            status_cb=self.statusBar().showMessage,
        )


def run_gui(
    debug_log: bool = False,
    dev: bool = False,
    *,
    task_mode: AcquisitionMode = "vast",
) -> int:
    from .launcher import run_mode_gui

    return run_mode_gui(task_mode, debug_log=debug_log, dev=dev)


def build_window(
    dev: bool = False,
    *,
    task_mode: AcquisitionMode = "vast",
) -> MainWindow:
    if not HAS_QT:
        raise RuntimeError(QT_ERROR_MESSAGE)
    return MainWindow(task_mode=task_mode, dev=dev)
