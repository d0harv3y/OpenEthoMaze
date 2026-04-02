"""
Main controller GUI: profile, calibration, config, run, export.

"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from ..profile import load_profile, save_profile, gui_to_dict
from ..h5_writer import open_db
from ..recording import TrialRecorder
from .. import app_logging
from ..shared_controller import config_center_xy
from ..task_registry import AcquisitionMode, get_task_spec
from .analysis_worker import AnalysisWorker
from .file_actions import (
    ask_trial_overwrite_merged,
    launch_h5web_for_path,
    next_keep_both_suffix,
)
from .identity import parse_virtual_video_identity, sanitize_session_id
from .mc_actions import flash_firmware, refresh_serial_ports, toggle_mc_connection
from .menus import build_main_window_menus
from .overlay_helpers import (
    draw_roi_and_tracking_overlay,
    resolve_exit_success_override,
)
from .pose_jump_state import PoseJumpState
from .profile_settings import (
    HAS_QT as HAS_QT_SETTINGS,
    read_last_profile_path,
    read_reload_last_profile,
    save_last_profile_path,
    write_reload_last_profile,
)
from .qt_preview import frame_to_pixmap

QT_ERROR_MESSAGE = "PySide6 is required for the GUI. Install with: pip install PySide6"
DEFAULT_WINDOW_SIZE = (500, 400)


try:
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLineEdit,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QSlider,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt, QRegularExpression, QTimer, QEvent, QUrl
    from PySide6.QtGui import QRegularExpressionValidator
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
        apply_display_adjustments,
        map_click_to_image_coords,
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
        self._last_preview_img_size: Optional[Tuple[int, int]] = None  # (width, height) for click mapping
        self._last_track_xy: Optional[Tuple[float, float]] = None  # latest valid tracking position for run loop
        self._pose_jump_state = PoseJumpState()
        self._tracking_controller = TrackingController(self._config) if HAS_TRACKING and TrackingController is not None else None
        self._camera_controller = CameraController(self._config) if HAS_CAMERA else None
        self._display_fps_times: list = []  # ring of frame timestamps for display FPS (max 30)
        self._display_fps_max_samples = 30
        self._last_display_fps: float = 0.0  # latest preview FPS estimate for dev HUD
        self._last_frame_timings: Optional[Tuple[float, float]] = None  # (read_ms, process_ms) for tooltip
        # Virtual acquisition: during idle (before Start trial), pause video frame advancement
        # so playback starts exactly when Start trial is pressed.
        self._virtual_video_path: Optional[Path] = None
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
        self._analysis_worker: Optional["AnalysisWorker"] = None
        self._central = QWidget()
        self.setCentralWidget(self._central)
        layout = QVBoxLayout(self._central)

        # Camera preview
        camera_section = SectionWithSettings("Camera", "Open Settings → Task") if SectionWithSettings else QGroupBox("Camera")
        camera_ly = camera_section.content_layout() if SectionWithSettings else QVBoxLayout()
        if not SectionWithSettings:
            camera_section.setLayout(camera_ly)
        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel("Source:"))
        self._camera_source = QComboBox()
        self._camera_source.addItem("OpenCV")
        if HAS_VIMBA:
            self._camera_source.addItem("GigE (Vimba)")
        self._camera_source.addItem("Virtual (video file)")
        self._camera_source.setToolTip("OpenCV = USB/DirectShow index. GigE = Allied Vision (e.g. Manta) via Vimba.")
        cam_row.addWidget(self._camera_source)
        cam_row.addWidget(QLabel("Device:"))
        self._camera_device = QSpinBox()
        self._camera_device.setRange(0, 15)
        self._camera_device.setValue(0)
        self._camera_device.setToolTip("OpenCV: index 0,1,… . GigE: device index (0=first).")
        cam_row.addWidget(self._camera_device)
        self._camera_start_btn = QPushButton("Start camera", clicked=self._on_start_camera)
        self._camera_stop_btn = QPushButton("Stop camera", clicked=self._on_stop_camera)
        self._camera_stop_btn.setEnabled(False)
        cam_row.addWidget(self._camera_start_btn)
        cam_row.addWidget(self._camera_stop_btn)
        self._camera_flip = QCheckBox("Flip image")
        cam_row.addWidget(self._camera_flip)
        camera_ly.addLayout(cam_row)
        # Display brightness/contrast (preview only)
        display_row = QHBoxLayout()
        display_row.addWidget(QLabel("Brightness:"))
        self._display_brightness = QSlider(Qt.Orientation.Horizontal)
        self._display_brightness.setRange(-100, 100)
        self._display_brightness.setValue(0)
        self._display_brightness.setToolTip("Display brightness offset (-100 to 100)")
        display_row.addWidget(self._display_brightness)
        self._display_brightness_label = QLabel("0")
        display_row.addWidget(self._display_brightness_label)
        display_row.addWidget(QLabel("Contrast:"))
        self._display_contrast = QSlider(Qt.Orientation.Horizontal)
        self._display_contrast.setRange(50, 200)
        self._display_contrast.setValue(100)
        self._display_contrast.setToolTip("Display contrast (50%–200%; 100% = no change)")
        display_row.addWidget(self._display_contrast)
        self._display_contrast_label = QLabel("100%")
        display_row.addWidget(self._display_contrast_label)
        display_row.addWidget(QLabel("Overlay opacity:"))
        self._track_opacity = QSlider(Qt.Orientation.Horizontal)
        self._track_opacity.setRange(0, 100)
        self._track_opacity.setValue(70)
        self._track_opacity.setToolTip("Tracking overlay opacity (0–100%).")
        display_row.addWidget(self._track_opacity)
        self._track_opacity_label = QLabel("70%")
        display_row.addWidget(self._track_opacity_label)
        camera_ly.addLayout(display_row)
        self._camera_label = QLabel()
        self._camera_label.setMinimumSize(320, 240)
        self._camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_label.setText("No camera" if not HAS_CAMERA else "Click Start camera")
        self._camera_label.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self._camera_label.setMouseTracking(True)
        camera_ly.addWidget(self._camera_label)
        # Set arena checkbox and tracking indicators on one row
        arena_track_row = QHBoxLayout()
        roi_click_text = (
            "Place RAM template from next click on preview"
            if self._task_mode == "ram"
            else "Set arena center from next click on preview"
        )
        self._roi_set_center_click = QCheckBox(roi_click_text)
        arena_track_row.addWidget(self._roi_set_center_click)
        arena_track_row.addWidget(QLabel("Source:"))
        self._track_source_label = QLabel("—")
        self._track_source_label.setToolTip("Current frame: SLEAP or Fallback")
        arena_track_row.addWidget(self._track_source_label)
        arena_track_row.addWidget(QLabel("Display FPS:"))
        self._track_display_fps_label = QLabel("—")
        self._track_display_fps_label.setToolTip("Preview frame rate")
        arena_track_row.addWidget(self._track_display_fps_label)
        arena_track_row.addWidget(QLabel("Frame:"))
        self._frame_counter_label = QLabel("—")
        self._frame_counter_label.setToolTip("Virtual/preview frame index (and total if known)")
        arena_track_row.addWidget(self._frame_counter_label)
        arena_track_row.addWidget(QLabel("Video:"))
        self._video_filename_label = QLabel("—")
        self._video_filename_label.setToolTip("Current virtual video filename")
        arena_track_row.addWidget(self._video_filename_label)
        arena_track_row.addStretch()
        camera_ly.addLayout(arena_track_row)
        layout.addWidget(camera_section)
        if SectionWithSettings:
            camera_section.settings_clicked.connect(
                lambda: self._on_open_settings_to_tab("task")
            )

        # MC (microcontroller) panel: COM port, Connect, status
        mc_section = QGroupBox("MC")
        mc_ly = QHBoxLayout()
        mc_section.setLayout(mc_ly)
        mc_ly.addWidget(QLabel("COM port:"))
        self._mc_port_combo = QComboBox()
        self._mc_port_combo.setMinimumWidth(180)
        self._mc_port_combo.setToolTip("Serial port for vibration controller (Arduino).")
        mc_ly.addWidget(self._mc_port_combo)
        self._mc_refresh_btn = QPushButton("Refresh", clicked=self._on_mc_refresh_ports)
        mc_ly.addWidget(self._mc_refresh_btn)
        self._mc_connect_btn = QPushButton("Connect", clicked=self._on_mc_connect)
        mc_ly.addWidget(self._mc_connect_btn)
        self._mc_flash_btn = QPushButton("Flash firmware", clicked=self._on_mc_flash)
        self._mc_flash_btn.setToolTip("Compile and upload firmware via arduino-cli (dev only; run with -d/--dev).")
        self._mc_flash_btn.setEnabled(dev)
        mc_ly.addWidget(self._mc_flash_btn)
        self._mc_status_label = QLabel("Disconnected")
        self._mc_status_label.setStyleSheet("color: gray;")
        self._mc_status_label.setToolTip("MC connection status")
        mc_ly.addWidget(self._mc_status_label)
        mc_ly.addStretch()
        layout.addWidget(mc_section)
        if not HAS_SERIAL or ArduinoStimulus is None:
            self._mc_port_combo.setEnabled(False)
            self._mc_refresh_btn.setEnabled(False)
            self._mc_connect_btn.setEnabled(False)
            self._mc_flash_btn.setEnabled(False)
            self._mc_status_label.setText("pyserial required")
        else:
            self._on_mc_refresh_ports()

        # Output folder (main layout)
        out_section = SectionWithSettings("Output", "Open Settings → Session") if SectionWithSettings else QGroupBox("Output")
        out_ly = QHBoxLayout()
        if SectionWithSettings:
            out_section.content_layout().addLayout(out_ly)
        else:
            out_section.setLayout(out_ly)
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setPlaceholderText("Folder for H5 file; videos in <h5_stem>_vids subfolder")
        out_ly.addWidget(self._output_dir_edit)
        self._output_browse_btn = QPushButton("Browse…", clicked=self._on_browse_output)
        out_ly.addWidget(self._output_browse_btn)
        layout.addWidget(out_section)
        if SectionWithSettings:
            out_section.settings_clicked.connect(
                lambda: self._on_open_settings_to_tab("session")
            )

        # Session controls (session ID, run mode)
        session_section = SectionWithSettings("Session controls", "Open Settings → Session") if SectionWithSettings else QGroupBox("Session controls")
        session_ly = QHBoxLayout()
        if SectionWithSettings:
            session_section.content_layout().addLayout(session_ly)
        else:
            session_section.setLayout(session_ly)
        out_ly.addWidget(QLabel("H5 file:"))
        self._h5_filename_edit = QLineEdit()
        self._h5_filename_edit.setPlaceholderText("trials.h5")
        self._h5_filename_edit.setToolTip("Filename for the H5 database in the output folder.")
        out_ly.addWidget(self._h5_filename_edit)
        session_ly.addWidget(QLabel("Session ID:"))
        self._session_id_edit = QLineEdit()
        self._session_id_edit.setPlaceholderText("e.g. 2025-02-19-A")
        self._session_id_edit.setToolTip("Letters, digits, hyphen, period only (no underscore; used as delimiter in filenames).")
        if HAS_QT:
            session_id_validator = QRegularExpressionValidator(
                QRegularExpression(r"^[a-zA-Z0-9.\-]*$")
            )
            self._session_id_edit.setValidator(session_id_validator)
        session_ly.addWidget(self._session_id_edit)
        self._phase_label = QLabel(self._task_spec.phase_label or "Phase:")
        session_ly.addWidget(self._phase_label)
        self._phase_combo = QComboBox()
        for label, value in self._task_spec.phase_options:
            self._phase_combo.addItem(label, value)
        session_ly.addWidget(self._phase_combo)
        session_ly.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        for label, value in self._task_spec.mode_options:
            self._mode_combo.addItem(label, value)
        session_ly.addWidget(self._mode_combo)
        show_phase = bool(self._task_spec.phase_options)
        self._phase_label.setVisible(show_phase)
        self._phase_combo.setVisible(show_phase)
        self._session_id_edit.textChanged.connect(self._on_session_controls_changed)
        self._phase_combo.currentIndexChanged.connect(self._on_session_controls_changed)
        self._mode_combo.currentIndexChanged.connect(self._on_session_controls_changed)
        self._h5_filename_edit.textChanged.connect(self._on_session_controls_changed)
        layout.addWidget(session_section)
        if SectionWithSettings:
            session_section.settings_clicked.connect(
                lambda: self._on_open_settings_to_tab("session")
            )

        # Status (state, trial, exit, animal, timers, duty)
        status_g = QGroupBox("Status")
        status_ly = QVBoxLayout()
        status_g.setLayout(status_ly)
        status_row1 = QHBoxLayout()
        status_row1.addWidget(QLabel("State:"))
        self._status_state = QLabel("—")
        status_row1.addWidget(self._status_state)
        status_row1.addWidget(QLabel("Animal ID:"))
        self._status_animal_id = QLabel("—")
        status_row1.addWidget(self._status_animal_id)
        status_row1.addWidget(QLabel("Trial:"))
        self._status_trial = QLabel("—")
        status_row1.addWidget(self._status_trial)
        # status_row2 = QHBoxLayout()
        status_row1.addWidget(QLabel(self._task_spec.exit_status_label))
        self._status_exit = QLabel("—")
        status_row1.addWidget(self._status_exit)
        status_row1.addWidget(QLabel("ITI:"))
        self._status_iti = QLabel("—")
        status_row1.addWidget(self._status_iti)
        status_row1.addWidget(QLabel("Trial timer:"))
        self._status_trial_timer = QLabel("—")
        status_row1.addWidget(self._status_trial_timer)
        status_row1.addWidget(QLabel("Duty %:"))
        self._status_duty = QLabel("—")
        self._status_duty.setToolTip("Feedback intensity that would be written (from current position)")
        status_row1.addWidget(self._status_duty)
        status_ly.addLayout(status_row1)
        # status_ly.addLayout(status_row2)
        layout.addWidget(status_g)

        # Run
        run_g = QGroupBox("Run")
        run_ly = QHBoxLayout()
        run_g.setLayout(run_ly)
        self._start_trial_btn = QPushButton("Start trial", clicked=self._on_start_trial)
        run_ly.addWidget(self._start_trial_btn)
        self._previous_trial_btn = QPushButton("Previous trial", clicked=self._on_previous_trial)
        run_ly.addWidget(self._previous_trial_btn)
        self._next_trial_btn = QPushButton("Next trial", clicked=self._on_next_trial)
        run_ly.addWidget(self._next_trial_btn)
        self._end_trial_btn = QPushButton("Manual Success", clicked=self._on_end_trial)
        self._end_trial_btn.setEnabled(False)
        run_ly.addWidget(self._end_trial_btn)
        self._stop_btn = QPushButton("Stop", clicked=self._on_stop)
        run_ly.addWidget(self._stop_btn)
        self._run_analysis_after_trial_cb = QCheckBox("Run analysis after each trial")
        self._run_analysis_after_trial_cb.setToolTip(
            "Run the maze pipeline (metrics, heatmap, movement bouts) when a trial ends. Requires maze.pipeline."
        )
        run_ly.addWidget(self._run_analysis_after_trial_cb)
        layout.addWidget(run_g)

        self._track_opacity.valueChanged.connect(self._on_track_opacity_changed)
        self._display_brightness.valueChanged.connect(self._on_display_brightness_changed)
        self._display_contrast.valueChanged.connect(self._on_display_contrast_changed)
        self._camera_label.installEventFilter(self)
        self._build_menus()
        if not HAS_CAMERA:
            self._camera_start_btn.setEnabled(False)
            self._camera_label.setText("Camera unavailable (install opencv-python)")
        if not HAS_TRACKING:
            pass  # Tracking options are in Settings → Tracking
        layout.addStretch()
        self.statusBar().showMessage("Ready. Load a profile or configure session.")
        self._apply_startup_profile()

    def _update_window_title(self) -> None:
        prefix = f"{self._task_spec.window_title} ({self._task_spec.display_name})"
        if self._profile_path:
            self.setWindowTitle(f"{prefix} — {self._profile_path}")
        else:
            self.setWindowTitle(f"{prefix} — Unsaved")

    def _on_track_opacity_changed(self, value: int) -> None:
        self._track_opacity_label.setText(f"{value}%")

    def _reset_sleap_node_jump_state(self) -> None:
        """Clear GUI-side SLEAP node max-jump memory (``_last_pose_xy`` and per-node streaks).

        Call sites should match any event that invalidates comparing the current pose to a stored
        reference in image space:

        - Virtual file playback: OpenCV frame index decreases (loop or seek backward).
        - **Confirmed** per-node teleport: a keypoint stays beyond ``node_max_jump_px`` for
          ``node_jump_confirm_frames`` consecutive frames (see ``_update_pose_last_and_valid``).
        - Settings Apply / ``_invalidate_tracker_cache`` (model path, backup-only, confidence, etc.).
        - Toggling **Flip image** (horizontal mirror swaps x).
        - Overlay ``track_source`` switches between ``sleap`` and ``fallback``.
        - Skeleton / node count change is handled by re-init when ``pose_xy`` shape mismatches
          ``_last_pose_xy`` (equivalent to clearing state).
        """
        self._pose_jump_state.reset()

    def _invalidate_tracker_cache(self) -> None:
        self._reset_sleap_node_jump_state()
        if self._tracking_controller is not None:
            path = self._config.sleap_model_path or ""
            backup_only = self._config.track_backup_only
            self._tracking_controller.set_sleap_params(path.strip(), backup_only)

    def _update_pose_last_and_valid(
        self,
        pose_xy: Optional[np.ndarray],
        node_max_jump_px: float,
        node_jump_confirm_frames: int,
    ) -> Optional[np.ndarray]:
        """Update ``_last_pose_xy``; return per-node validity (finite and within max jump, or debounced).

        When ``node_max_jump_px > 0``, a node that moves farther than that vs the last accepted
        position is marked invalid for up to ``node_jump_confirm_frames - 1`` consecutive frames.
        After that many consecutive over-threshold frames, all jump state is reset from the
        current pose (same effect as Apply). ``node_jump_confirm_frames == 1`` resets on the
        first over-threshold frame.
        """
        return self._pose_jump_state.update(
            pose_xy=pose_xy,
            node_max_jump_px=node_max_jump_px,
            node_jump_confirm_frames=node_jump_confirm_frames,
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
        )

    def _on_save_profile_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save profile as", "", "JSON (*.json);;All (*)"
        )
        if path:
            try:
                self._apply_ui_to_config()
                snapshot = self._trial_controller.get_session_snapshot()
                session_id, trial_idx, slot_idx = (snapshot if snapshot else (None, None, None))
                gui = gui_to_dict(
                    track_show=self._config.track_show,
                    track_async=self._config.track_async,
                    track_backup_only=self._config.track_backup_only,
                    track_sleap_path=self._config.sleap_model_path or "",
                    track_confidence=self._config.sleap_confidence_pct,
                    track_sleap_every_n=self._config.sleap_every_n,
                    track_opacity=self._track_opacity.value(),
                    display_brightness=self._display_brightness.value(),
                    display_contrast=self._display_contrast.value(),
                    camera_flip=self._camera_flip.isChecked(),
                    camera_source=self._camera_source.currentText(),
                    camera_device=self._camera_device.value(),
                    arduino_port=(self._mc_port_combo.currentData() or self._mc_port_combo.currentText() or "").strip(),
                )
                save_profile(self._config, Path(path), session_id=session_id, trial_idx=trial_idx, slot_idx=slot_idx, gui=gui)
                self._profile_path = Path(path)
                self._update_window_title()
                self._save_last_profile_path()
                self.statusBar().showMessage(f"Saved {path}")
            except Exception as e:
                self.statusBar().showMessage(f"Save failed: {e}")

    def _on_open_profile_in_editor(self) -> None:
        if not self._profile_path or not self._profile_path.exists():
            self.statusBar().showMessage("Save profile first.")
            return
        if HAS_DESKTOP_SERVICES:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._profile_path)))
            self.statusBar().showMessage("Opened profile in editor.")
        else:
            self.statusBar().showMessage("Cannot open in editor (QDesktopServices unavailable).")

    def _on_reload_profile(self) -> None:
        if not self._profile_path or not self._profile_path.exists():
            self.statusBar().showMessage("No profile loaded.")
            return
        try:
            self._config, session_id, ti, gui, slot = load_profile(self._profile_path)
            session_id_safe = sanitize_session_id(session_id) if session_id else ""
            self._apply_config_to_ui(gui=gui)
            dlg = getattr(self, "_settings_dialog", None)
            if dlg is not None and hasattr(dlg, "set_config"):
                dlg.set_config(self._config)
            self._trial_controller = self._task_spec.controller_factory(self._config)
            self._trial_controller.add_state_listener(self._on_trial_state_change)
            self._trial_controller.reset(session_id_safe, ti, slot_idx=slot)
            if session_id_safe:
                self._session_id_edit.setText(session_id_safe)
            self._update_window_title()
            self._save_last_profile_path()
            self._apply_status_and_buttons()
            self.statusBar().showMessage(f"Reloaded {self._profile_path}")
        except Exception as e:
            self.statusBar().showMessage(f"Reload failed: {e}")

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

    _SETTINGS_TAB_NAMES = ("Task", "Session", "Animals", "Tracking")

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

    def _on_open_settings_to_tab(self, tab_name: str | int) -> None:
        if not HAS_SETTINGS_DIALOG or SettingsDialog is None:
            self.statusBar().showMessage("Settings dialog unavailable.")
            return
        if isinstance(tab_name, str):
            normalized = tab_name.strip().lower()
            tab_index = {
                "task": 0,
                "session": 1,
                "animals": 2,
                "tracking": 3,
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
            dlg.accepted.connect(lambda: (self._apply_config_to_ui(), self.statusBar().showMessage("Settings applied.")))
        else:
            dlg.set_current_tab(tab_index)
        tab_name = self._SETTINGS_TAB_NAMES[tab_index] if 0 <= tab_index < len(self._SETTINGS_TAB_NAMES) else "Settings"
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
        self.statusBar().showMessage(message if message else ("Analysis done" if success else "Analysis failed"))

    def _on_end_trial(self) -> None:
        msg = self._trial_controller.do_end_trial()
        self._apply_status_and_buttons()
        self.statusBar().showMessage(msg)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._camera_label and event.type() == QEvent.Type.MouseButtonPress:
            if self._roi_set_center_click.isChecked() and self._camera_controller is not None:
                size = self._camera_controller.get_last_preview_size()
                if size is not None:
                    iw, ih = size
                    if iw > 0 and ih > 0:
                        lw, lh = self._camera_label.width(), self._camera_label.height()
                        lx, ly = event.position().x(), event.position().y()
                        ix, iy = map_click_to_image_coords(
                            lx,
                            ly,
                            lw,
                            lh,
                            iw,
                            ih,
                        )
                        if self._task_mode == "ram" and hasattr(self._config, "radial_arm"):
                            self._config.radial_arm.calibration.template_center_x_px = float(ix)
                            self._config.radial_arm.calibration.template_center_y_px = float(iy)
                            message = f"RAM template center set to ({ix}, {iy})"
                        else:
                            self._config.arena.arena_center_x_px = float(ix)
                            self._config.arena.arena_center_y_px = float(iy)
                            message = f"Arena center set to ({ix}, {iy})"
                        self._roi_set_center_click.setChecked(False)
                        self.statusBar().showMessage(message)
        return super().eventFilter(obj, event)

    def _on_camera_tick(self) -> None:
        if self._camera_controller is None:
            return
        virtual_mode = bool(
            self._camera_source.currentText().startswith("Virtual")
            if self._camera_source is not None
            else False
        )
        tc = self._trial_controller

        # Virtual pause behavior:
        # - when not running, freeze *video advancement* but still re-render overlays
        #   from the cached first frame so settings changes take effect immediately.
        paused_virtual = virtual_mode and not tc.run_active
        if paused_virtual:
            if self._virtual_cached_frame_raw is None:
                t0 = time.perf_counter()
                img_raw = self._camera_controller.grab_frame()
                t1 = time.perf_counter()
                if img_raw is None:
                    return
                self._virtual_cached_frame_raw = img_raw
                self._virtual_has_initial_frame = True
                self._virtual_cached_frame_index, _ = self._camera_controller.get_last_frame_info()
            else:
                img_raw = self._virtual_cached_frame_raw
                t0 = time.perf_counter()
                t1 = t0
        else:
            # When running, discard any paused cache so playback resumes from the camera.
            self._virtual_has_initial_frame = False
            self._virtual_cached_frame_raw = None
            self._virtual_cached_frame_index = None
            self._last_virtual_playback_frame_idx = None
            t0 = time.perf_counter()
            img_raw = self._camera_controller.grab_frame()
            t1 = time.perf_counter()
        if img_raw is not None:
            if virtual_mode:
                # In virtual mode, the cached paused frame will be used while paused.
                # When running, the cache was cleared above.
                pass
            # Display FPS (rolling average)
            now = time.monotonic()
            self._display_fps_times.append(now)
            if len(self._display_fps_times) > self._display_fps_max_samples:
                self._display_fps_times.pop(0)
            if len(self._display_fps_times) >= 2:
                span = self._display_fps_times[-1] - self._display_fps_times[0]
                fps = (len(self._display_fps_times) - 1) / span if span > 0 else 0
                self._last_display_fps = float(fps)
                self._track_display_fps_label.setText(f"{fps:.1f}")
            else:
                self._track_display_fps_label.setText("—")

            # Frame index indicator (use camera controller's last seen info).
            if hasattr(self, "_frame_counter_label") and self._frame_counter_label is not None:
                if virtual_mode:
                    # Trial-relative: before Start trial, show 0 even if we already grabbed a cached preview frame.
                    cur_idx, total = self._camera_controller.get_last_frame_info()
                    if not tc.run_active:
                        if total is not None and total > 0:
                            self._frame_counter_label.setText(f"0/{total}")
                        else:
                            self._frame_counter_label.setText("0/—")
                    elif cur_idx is None or cur_idx < 0:
                        self._frame_counter_label.setText("—")
                    else:
                        cur_1b = cur_idx + 1
                        if total is not None and total > 0:
                            self._frame_counter_label.setText(f"{cur_1b}/{total}")
                        else:
                            self._frame_counter_label.setText(f"{cur_1b}/—")
                else:
                    self._frame_counter_label.setText("—")
            # Raw frame for inference (no brightness/contrast); display uses a copy with adjustments
            flip_now = self._camera_flip.isChecked()
            if self._last_preview_flip_checked is not None and flip_now != self._last_preview_flip_checked:
                self._reset_sleap_node_jump_state()
            self._last_preview_flip_checked = flip_now
            if flip_now and _cv2 is not None:
                img_raw = _cv2.flip(img_raw, 1)  # 1 = horizontal (flip x-axis)
            h, w = img_raw.shape[0], img_raw.shape[1]
            self._last_preview_img_size = (w, h)
            # Virtual file playback: frame index went backward → video looped or seek; reset GUI pose-jump state.
            if virtual_mode and not paused_virtual and self._camera_controller is not None:
                playback_cur_idx, _ = self._camera_controller.get_last_frame_info()
                if playback_cur_idx is not None and self._last_virtual_playback_frame_idx is not None:
                    if playback_cur_idx < self._last_virtual_playback_frame_idx:
                        self._reset_sleap_node_jump_state()
                if playback_cur_idx is not None:
                    self._last_virtual_playback_frame_idx = playback_cur_idx
            # Display copy: brightness/contrast and BGR for overlay
            img_display = apply_display_adjustments(
                img_raw.copy(),
                self._display_brightness.value(),
                self._display_contrast.value(),
            )
            if _cv2 is not None and img_display.ndim == 2:
                img_display = _cv2.cvtColor(img_display, _cv2.COLOR_GRAY2BGR)
            show_track = self._config.track_show and HAS_TRACKING and AdaptiveThresholdTracker is not None
            a = self._config.arena
            roi_cx = a.arena_center_x_px
            roi_cy = a.arena_center_y_px
            roi_r = a.radius_px
            roi_center = (roi_cx, roi_cy) if roi_r > 0 else None
            track_xy, track_valid = None, False
            track_source = "fallback"
            pose_xy, pose_scores, pose_edge_inds, pose_node_names = None, None, None, None
            pose_node_valid_from_res = None  # per-node confidence validity from tracker (SLEAP only)
            blob_mask = None
            blob_crop_rect = None
            if show_track and self._tracking_controller is not None:
                to_track = img_raw  # inference sees raw image (no brightness/contrast)
                track_r = a.tracking_mask_radius_px
                did_crop = False
                crop_x0, crop_y0 = 0, 0  # offset to add to tracker coords when we crop
                if _cv2 is not None and track_r > 0:
                    # Crop to rectangle around circle so tracker runs on fewer pixels (better FPS).
                    # Display still shows full image; we add crop offset to track_xy/pose_xy and embed blob_mask.
                    crop_x0 = max(0, int(roi_cx - track_r) - 1)
                    crop_y0 = max(0, int(roi_cy - track_r) - 1)
                    crop_x1 = min(w, int(roi_cx + track_r) + 2)
                    crop_y1 = min(h, int(roi_cy + track_r) + 2)
                    if crop_x1 > crop_x0 and crop_y1 > crop_y0:
                        did_crop = True
                        to_track = img_raw[crop_y0:crop_y1, crop_x0:crop_x1].copy()
                        # Apply circular mask within crop (center relative to crop)
                        cx_crop = roi_cx - crop_x0
                        cy_crop = roi_cy - crop_y0
                        mask_crop = np.zeros(to_track.shape[:2], dtype=np.uint8)
                        _cv2.circle(
                            mask_crop,
                            (int(cx_crop), int(cy_crop)),
                            int(track_r),
                            255,
                            -1,
                        )
                        to_track = _cv2.bitwise_and(to_track, to_track, mask=mask_crop)
                # Update SLEAP parameters on the controller and submit frame
                path = self._config.sleap_model_path or ""
                self._tracking_controller.set_sleap_params(path.strip(), self._config.track_backup_only)
                now = time.monotonic()
                self._tracking_controller.submit_frame(to_track, now)
                overlay_state = self._tracking_controller.get_overlay_state(now_s=now)
                track_xy_res = overlay_state["track_xy"]
                track_valid_res = overlay_state["track_valid"]
                track_source = overlay_state["track_source"]
                pose_xy = overlay_state["pose_xy"]
                pose_scores = overlay_state["pose_scores"]
                pose_edge_inds = overlay_state["pose_edge_inds"]
                pose_node_names = overlay_state["pose_node_names"]
                pose_node_valid_from_res = overlay_state["pose_node_valid"]
                blob_mask_res = overlay_state["blob_mask"]
                in_range_xy_res = overlay_state.get("in_range_xy")
                # If we cropped, convert from crop coords to full-image coords.
                # Pass small blob_mask + crop rect so overlay blends only in that slice (no full-frame alloc).
                if did_crop:
                    if track_xy_res is not None:
                        track_xy_res = (track_xy_res[0] + crop_x0, track_xy_res[1] + crop_y0)
                    if pose_xy is not None and pose_xy.size > 0:
                        pose_xy = np.asarray(pose_xy, dtype=np.float64) + np.array([crop_x0, crop_y0])
                    blob_mask = blob_mask_res
                    blob_crop_rect = (crop_x0, crop_y0, crop_x1, crop_y1) if blob_mask_res is not None else None
                else:
                    blob_mask = blob_mask_res
                    blob_crop_rect = None
                if track_xy_res is not None:
                    track_xy = track_xy_res
                    track_valid = track_valid_res
                    if track_valid:
                        self._last_track_xy = track_xy
                else:
                    # No result yet: keep last position for overlay but mark invalid.
                    track_xy = getattr(self, "_last_track_xy", None)
                    track_valid = False
                self._track_source_label.setText(overlay_state["source_label"])
                if self._last_overlay_track_source is not None and track_source != self._last_overlay_track_source:
                    self._reset_sleap_node_jump_state()
                self._last_overlay_track_source = track_source

                # Minimal SLEAP device debug (once per session / device change).
                if (
                    self._last_sleap_device_logged is None
                    or (time.monotonic() - (self._last_sleap_log_time_s or 0.0)) > 2.0
                ):
                    try:
                        sleap_label, sleap_tip = self._tracking_controller.get_sleap_status_label()
                        key = sleap_tip or sleap_label
                        if key and key != self._last_sleap_device_logged:
                            # Help->View error log: minimal one-line device info or load failure reason.
                            self._gui_log_error(f"SLEAP: {sleap_tip}")
                            self._last_sleap_device_logged = key
                            self._last_sleap_log_time_s = time.monotonic()
                    except Exception:
                        # Best-effort debug; never break preview.
                        pass
            else:
                # show_track is False: no tracking overlay
                self._track_source_label.setText("—")
                self._last_overlay_track_source = None
            opacity = self._track_opacity.value() / 100.0
            if show_track or (roi_center is not None and roi_r > 0):
                ft = self._config.fallback_tracking
                node_max_jump_px = ft.node_max_jump_px
                node_jump_confirm = max(1, int(getattr(ft, "node_jump_confirm_frames", 2)))
                pose_node_valid = self._update_pose_last_and_valid(
                    pose_xy, node_max_jump_px, node_jump_confirm
                )
                # Combine confidence-based validity (from tracker) with jump-based validity
                if (
                    pose_node_valid_from_res is not None
                    and pose_xy is not None
                    and pose_node_valid_from_res.shape == (pose_xy.shape[0],)
                    and pose_node_valid is not None
                    and pose_node_valid.shape == pose_node_valid_from_res.shape
                ):
                    pose_node_valid = pose_node_valid & pose_node_valid_from_res
                img_display = draw_roi_and_tracking_overlay(
                    img_display, roi_center, roi_r, track_xy, track_valid, opacity,
                    overlay_info=self._trial_controller.get_overlay_info(),
                    track_source=track_source,
                    pose_xy=pose_xy,
                    pose_scores=pose_scores,
                    pose_edge_inds=pose_edge_inds,
                    pose_node_names=pose_node_names,
                    pose_node_valid=pose_node_valid,
                    blob_mask=blob_mask,
                    blob_crop_rect=blob_crop_rect,
                )
            else:
                pose_node_valid = None
            tc = self._trial_controller
            exit_x_px, exit_y_px = tc.get_exit_position_px()
            exit_success_override = None
            if self._task_mode == "vast":
                exit_radius_px = (
                    self._config.arena.exit_radius_cm * self._config.arena.px_per_cm
                )
                required_kp = max(
                    1, int(getattr(self._config, "sleap_exit_min_keypoints", 2))
                )
                min_frac = max(
                    0.0,
                    min(
                        1.0,
                        float(
                            getattr(
                                self._config,
                                "fallback_exit_blob_overlap_pct",
                                15.0,
                            )
                        )
                        / 100.0,
                    ),
                )
                exit_success_override = resolve_exit_success_override(
                    pose_xy=pose_xy,
                    pose_node_valid=pose_node_valid,
                    pose_node_names=pose_node_names,
                    blob_mask=blob_mask,
                    blob_crop_rect=blob_crop_rect,
                    track_xy=track_xy,
                    track_source=track_source,
                    exit_x_px=exit_x_px,
                    exit_y_px=exit_y_px,
                    exit_radius_px=exit_radius_px,
                    arena=self._config.arena,
                    required_keypoints=required_kp,
                    min_blob_overlap_fraction=min_frac,
                    allow_either_success=bool(
                        getattr(self._config, "track_exit_either_success", False)
                    ),
                )
            tc.set_exit_success_override(exit_success_override)
            x_px = float(self._last_track_xy[0]) if self._last_track_xy is not None else (roi_cx or 0.0)
            y_px = float(self._last_track_xy[1]) if self._last_track_xy is not None else (roi_cy or 0.0)
            duty_pct = tc.get_duty_for_position(x_px, y_px)
            if self._arduino_stimulus is not None and self._arduino_stimulus.connected:
                self._arduino_stimulus.set_duty(duty_pct)
                for cmd in self._arduino_stimulus.read_pending_commands():
                    if cmd == "T":
                        self._on_start_trial()
                        break
            # Per-trial recording: record entire trial slot (ITI + wait + trial) until SUCCESS/TIMEOUT
            output_dir = self._config.output_dir
            if tc.is_recording_trial() and output_dir:
                out_path = Path(output_dir)
                h5_name = (self._config.h5_filename or "trials.h5").strip() or "trials.h5"
                if Path(h5_name).name != h5_name:
                    h5_name = Path(h5_name).name
                db_path = out_path / h5_name
                # Videos go in a subfolder named after the H5 file with _vids suffix (e.g. trials_vids)
                video_dir = out_path / f"{Path(h5_name).stem}_vids"
                x_px = 0.0
                y_px = 0.0
                if self._last_track_xy is not None:
                    x_px, y_px = float(self._last_track_xy[0]), float(self._last_track_xy[1])
                elif roi_cx is not None and roi_cy is not None:
                    x_px, y_px = float(roi_cx), float(roi_cy)
                exit_x, exit_y = tc.get_exit_position_px()
                duty_pct = tc.get_duty_for_position(x_px, y_px)
                dist_to_exit_px, in_exit = tc.get_recording_frame_metrics(x_px, y_px)
                trial_state_str = tc.get_trial_state_for_recording() or "iti"
                meta = tc.get_recording_metadata()
                if self._trial_recorder is None and meta is not None:
                    animal_id, session_id, trial = meta
                    self._trial_recorder = TrialRecorder(
                        output_dir=video_dir,
                        db_path=db_path,
                        animal_id=animal_id,
                        session_id=session_id,
                        trial=trial,
                        config=self._config,
                        run_mode=self._config.run_mode or "continuous",
                    )
                    frame_shape = (img_raw.shape[0], img_raw.shape[1])
                    if img_raw.ndim == 3:
                        frame_shape = img_raw.shape
                    self._trial_recorder.start(frame_shape=frame_shape, fps=30.0)
                    self._record_frame_index = 0
                if self._trial_recorder is not None:
                    try:
                        spot_xy_for_record: Optional[Tuple[float, float]] = None
                        in_range_xy_for_record: Optional[Tuple[float, float]] = None
                        centroid_xy_for_record: Optional[Tuple[float, float]] = None
                        if (
                            in_range_xy_res is not None
                            and len(in_range_xy_res) == 2
                            and np.isfinite(float(in_range_xy_res[0]))
                            and np.isfinite(float(in_range_xy_res[1]))
                        ):
                            in_range_xy_for_record = (
                                float(in_range_xy_res[0]),
                                float(in_range_xy_res[1]),
                            )
                        if track_valid and track_xy is not None:
                            if track_source == "sleap":
                                # Prefer SLEAP front-node mean for spot trajectory.
                                if (
                                    pose_xy is not None
                                    and pose_node_names is not None
                                    and pose_xy.ndim == 2
                                    and pose_xy.shape[1] == 2
                                    and len(pose_node_names) >= pose_xy.shape[0]
                                ):
                                    fore_names = {"nose", "neck", "foreL", "foreR"}
                                    pts: list[tuple[float, float]] = []
                                    for j in range(pose_xy.shape[0]):
                                        name = str(pose_node_names[j])
                                        if name not in fore_names:
                                            continue
                                        if pose_node_valid is not None and j < pose_node_valid.shape[0] and not bool(pose_node_valid[j]):
                                            continue
                                        xj = float(pose_xy[j, 0])
                                        yj = float(pose_xy[j, 1])
                                        if np.isfinite(xj) and np.isfinite(yj):
                                            pts.append((xj, yj))
                                    if pts:
                                        xs, ys = zip(*pts)
                                        spot_xy_for_record = (float(np.mean(xs)), float(np.mean(ys)))
                                # SLEAP centroid from all valid nodes.
                                if (
                                    pose_xy is not None
                                    and pose_xy.ndim == 2
                                    and pose_xy.shape[1] == 2
                                ):
                                    pts_all: list[tuple[float, float]] = []
                                    for j in range(pose_xy.shape[0]):
                                        if pose_node_valid is not None and j < pose_node_valid.shape[0] and not bool(pose_node_valid[j]):
                                            continue
                                        xj = float(pose_xy[j, 0])
                                        yj = float(pose_xy[j, 1])
                                        if np.isfinite(xj) and np.isfinite(yj):
                                            pts_all.append((xj, yj))
                                    if pts_all:
                                        xs_all, ys_all = zip(*pts_all)
                                        centroid_xy_for_record = (
                                            float(np.mean(xs_all)),
                                            float(np.mean(ys_all)),
                                        )
                                # Fallback to tracker point if front nodes aren't available this frame.
                                if spot_xy_for_record is None:
                                    spot_xy_for_record = (float(track_xy[0]), float(track_xy[1]))

                        self._trial_recorder.write_frame(
                            image=img_raw,
                            frame_index=self._record_frame_index,
                            x_px=x_px,
                            y_px=y_px,
                            dist_to_exit_px=dist_to_exit_px,
                            trial_state=trial_state_str,
                            in_exit_zone=in_exit,
                            valid=track_valid,
                            duty_pct=duty_pct,
                            spot_xy=spot_xy_for_record,
                            in_range_xy=in_range_xy_for_record,
                            centroid_xy=centroid_xy_for_record,
                        )
                        self._record_frame_index += 1
                    except Exception:
                        pass
            # Dev-only debug HUD overlay: draw simple text on the preview with per-frame diagnostics.
            if self._dev_mode and _cv2 is not None:
                try:
                    debug_lines = []
                    debug_lines.append(
                        f"FPS {self._last_display_fps:.1f}  read {((t1 - t0) * 1000):.1f} ms"
                    )
                    # process_ms is computed below; estimate it here as well for per-frame HUD
                    debug_lines.append(f"track src {track_source}")
                    y0 = 18
                    for line in debug_lines:
                        # Outline in black, then inner text in white for readability
                        _cv2.putText(
                            img_display,
                            line,
                            (8, y0),
                            _cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,
                            (0, 0, 0),
                            3,
                            _cv2.LINE_AA,
                        )
                        _cv2.putText(
                            img_display,
                            line,
                            (8, y0),
                            _cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,
                            (255, 255, 255),
                            1,
                            _cv2.LINE_AA,
                        )
                        y0 += 16
                except Exception:
                    # HUD is best-effort; never break preview if debug drawing fails
                    pass

            pix = frame_to_pixmap(img_display)
            if pix is not None:
                self._camera_label.setPixmap(pix.scaled(
                    self._camera_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
            # Frame timing for FPS investigation: hover Display FPS to see read vs process breakdown
            read_ms = (t1 - t0) * 1000
            process_ms = (time.perf_counter() - t1) * 1000
            self._last_frame_timings = (read_ms, process_ms)
            tt = "Preview frame rate."
            if self._last_frame_timings is not None:
                r, p = self._last_frame_timings
                tt += f" Last frame: read {r:.1f} ms, process {p:.1f} ms (track+overlay+display)."
            if hasattr(self, "_track_display_fps_label"):
                self._track_display_fps_label.setToolTip(tt)

    def _on_start_camera(self) -> None:
        if not HAS_CAMERA:
            return
        self._on_stop_camera()
        source = self._camera_source.currentText()
        # Reset virtual playback pause state; will be set again if user picks a video.
        self._virtual_video_path = None
        self._virtual_has_initial_frame = False
        self._virtual_cached_frame_raw = None
        self._virtual_cached_frame_index = None
        try:
            if self._camera_controller is not None:
                device_index = self._camera_device.value()
                video_path = None
                if source.startswith("Virtual"):
                    video_path_str, _ = QFileDialog.getOpenFileName(
                        self,
                        "Select video file for virtual acquisition",
                        "",
                        "Video files (*.mp4 *.avi *.mkv *.mov);;All files (*)",
                    )
                    if not video_path_str:
                        return
                    video_path = Path(video_path_str)
                    self._virtual_video_path = video_path
                    self._video_filename_label.setText(video_path.name)
                    self._video_filename_label.setToolTip(str(video_path))
                else:
                    self._video_filename_label.setText("—")
                    self._video_filename_label.setToolTip("Current virtual video filename")
                self._camera_controller.open(source, device_index, video_path=video_path)
                # Status message: keep simple for now; detailed backend info can
                # be added via CameraController hooks in the future.
                if video_path is not None:
                    self.statusBar().showMessage(f"Virtual video started ({source}): {video_path.name}")
                else:
                    self.statusBar().showMessage(f"Camera {device_index} started ({source}).")
            self._camera_timer = QTimer(self)
            self._camera_timer.setTimerType(Qt.TimerType.PreciseTimer)  # better accuracy on Windows for 30 FPS
            self._camera_timer.timeout.connect(self._on_camera_tick)
            # Target ~30 FPS; actual FPS limited by camera + processing (see Display FPS tooltip for breakdown)
            self._camera_timer.start(33)
            self._camera_start_btn.setEnabled(False)
            self._camera_stop_btn.setEnabled(True)
            # Start tracking controller (async or sync)
            if self._tracking_controller is not None:
                self._tracking_controller.start(async_enabled=self._config.track_async)
            self._apply_status_and_buttons()
        except Exception as e:
            self.statusBar().showMessage(f"Camera failed: {e}")
            if self._camera_controller is not None:
                self._camera_controller.close()

    def _on_stop_camera(self) -> None:
        if self._arduino_stimulus is not None and self._arduino_stimulus.connected:
            self._arduino_stimulus.set_duty(0)
        # Stop tracking controller
        if self._tracking_controller is not None:
            self._tracking_controller.stop()
        if self._camera_timer is not None:
            self._camera_timer.stop()
            self._camera_timer = None
        if self._camera_controller is not None:
            self._camera_controller.close()
        self._camera_start_btn.setEnabled(True)
        self._camera_stop_btn.setEnabled(False)
        self._camera_label.clear()
        self._camera_label.setText("Click Start camera")
        self.statusBar().showMessage("Camera stopped.")
        self._virtual_video_path = None
        self._video_filename_label.setText("—")
        self._video_filename_label.setToolTip("Current virtual video filename")
        self._virtual_has_initial_frame = False
        self._virtual_cached_frame_raw = None
        self._virtual_cached_frame_index = None
        self._apply_status_and_buttons()

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
        """True if camera is running and we can record video (required to run trials)."""
        return bool(
            HAS_CAMERA
            and self._camera_timer is not None
            and self._camera_timer.isActive()
        )

    def _is_mc_connected(self) -> bool:
        """True if MC (Arduino) is connected and correct firmware is running."""
        return bool(
            self._arduino_stimulus is not None and self._arduino_stimulus.connected
        )

    def _apply_status_and_buttons(self) -> None:
        """Apply trial controller status dict and button states to widgets. See docs/button_flow_state.md."""
        x, y = self._last_track_xy if self._last_track_xy else (0.0, 0.0)
        d = self._trial_controller.get_status_dict(x, y)
        self._status_state.setText(str(d["state"]))
        self._status_trial.setText(str(d["trial"]))
        self._status_exit.setText(str(d["exit"]))
        self._status_animal_id.setText(str(d["animal_id"]))
        self._status_iti.setText(str(d["iti"]))
        self._status_trial_timer.setText(str(d["trial_timer"]))
        self._status_duty.setText(str(d["duty"]))
        if d.get("session_id", "") != self._session_id_edit.text().strip():
            self._session_id_edit.setText(sanitize_session_id(str(d.get("session_id", ""))))
        bs = self._trial_controller.get_button_states()
        video_ok = self._is_video_available()
        mc_ok = self._is_mc_connected()
        # In dev mode, camera and MC are not required for run buttons.
        # For virtual acquisition (video file playback), allow running even if MC is not connected.
        virtual_mode = video_ok and self._camera_source.currentText().startswith("Virtual")
        device_ready = (
            (mc_ok or virtual_mode)
            if self._task_spec.requires_mc_connection
            else True
        )
        run_ok = self._dev_mode or (video_ok and device_ready)
        self._start_trial_btn.setEnabled(bs["start"] and run_ok)
        self._previous_trial_btn.setEnabled(bs["previous"] and run_ok)
        self._next_trial_btn.setEnabled(bs["next"] and run_ok)
        self._end_trial_btn.setEnabled(bs["end_trial"] and run_ok)
        self._stop_btn.setEnabled(bs["stop"] and run_ok)
        # Lock flip while session is active so coordinate space is stable for tracking/exit/H5.
        self._camera_flip.setEnabled(not self._trial_controller.run_active)
        self._sync_settings_apply_enabled()

    def _sync_settings_apply_enabled(self) -> None:
        dlg = getattr(self, "_settings_dialog", None)
        if dlg is None or not hasattr(dlg, "set_apply_enabled"):
            return
        tc = self._trial_controller
        dlg.set_apply_enabled(not tc.is_trial_running_phase())

    def _on_run_timer(self) -> None:
        now = time.monotonic()
        if self._run_timer_last_s is None:
            self._run_timer_last_s = now
            self._apply_status_and_buttons()
            return
        dt = now - self._run_timer_last_s
        self._run_timer_last_s = now
        if self._last_track_xy is not None:
            x, y = self._last_track_xy
        else:
            # Fall back to arena center instead of (0,0) so duty/exit logic
            # doesn't saturate when tracking is temporarily unavailable.
            x, y = config_center_xy(self._config)
        self._trial_controller.tick(x, y, dt)
        self._apply_status_and_buttons()

    def _on_stop_run(self) -> None:
        if self._arduino_stimulus is not None and self._arduino_stimulus.connected:
            self._arduino_stimulus.set_duty(0)
        if self._run_timer is not None:
            self._run_timer.stop()
            self._run_timer = None
        self._run_timer_last_s = None
        self._stop_trial_recorder_if_active()
        self._trial_controller.stop_run()
        self._apply_status_and_buttons()

    def _on_trial_state_change(self, new_state) -> None:
        """When trial ends (SUCCESS or TIMEOUT), advance slot first (so motors stop), then flush/clear recorder (may show duplicate popup)."""
        state_value = getattr(new_state, "value", str(new_state))
        if state_value not in {"trial_success", "trial_timeout"}:
            return
        # Advance trial so state is ITI/IDLE before any modal dialog; motors stop immediately
        self._trial_controller.stop_run()
        if self._arduino_stimulus is not None and self._arduino_stimulus.connected:
            self._arduino_stimulus.set_duty(0)
        self._apply_status_and_buttons()
        self._stop_trial_recorder_if_active()

    def _stop_trial_recorder_if_active(self) -> None:
        """If a trial recording is in progress, show one overwrite/discard/keep_both dialog for H5 and video conflicts, then stop or cancel."""
        if self._trial_recorder is None:
            return
        rec = self._trial_recorder
        exit_x, exit_y = self._trial_controller.get_exit_position_px()
        timestamp_str = datetime.now(timezone.utc).isoformat(timespec="seconds")
        existing_h5_key = f"/{rec.animal_id}/{rec.session_id}/{rec.trial}"
        final_video_path = rec.output_dir / f"{rec.animal_id}_{rec.session_id}_{rec.trial}.mp4"

        h5_conflict = False
        if rec.db_path.exists():
            try:
                with open_db(rec.db_path, "r") as h5:
                    if existing_h5_key in h5:
                        h5_conflict = True
            except Exception:
                pass
        video_conflict = final_video_path.exists()

        conflict_choice = None
        if h5_conflict or video_conflict:
            suffix = next_keep_both_suffix(
                rec.db_path,
                rec.output_dir,
                rec.animal_id,
                rec.session_id,
                rec.trial,
            )
            new_h5_key = f"/{rec.animal_id}/{rec.session_id}/{rec.trial}{suffix}"
            new_video_path = rec.output_dir / f"{rec.animal_id}_{rec.session_id}_{rec.trial}{suffix}.mp4"
            choice = ask_trial_overwrite_merged(
                self,
                h5_key=existing_h5_key if h5_conflict else None,
                video_path=final_video_path if video_conflict else None,
                new_h5_key_with_suffix=new_h5_key,
                new_video_path_with_suffix=new_video_path,
                keep_both_suffix=suffix,
            )
            if choice == "discard":
                try:
                    rec.cancel(delete_video=True)
                except Exception:
                    pass
                self._trial_recorder = None
                self._record_frame_index = 0
                return
            if choice != "overwrite":
                _, suffix = choice
                _, suffix_from_choice = choice
                rec.trial = rec.trial + (suffix_from_choice or "(2)")
            # Pass choice to recorder so it renames video to the right path (overwrite vs keep_both with new trial path)
            conflict_choice = choice if (video_conflict or choice != "overwrite") else None

        stop_ok = False
        try:
            rec.stop(
                exit_x_px=exit_x,
                exit_y_px=exit_y,
                timestamp_str=timestamp_str,
                conflict_choice=conflict_choice,
            )
            stop_ok = True
        except Exception as e:
            import traceback
            print(f"Error in TrialRecorder.stop: {e}")
            traceback.print_exc()
        # Capture trial info only when stop() succeeded, so analysis runs on a trial that was actually written
        run_analysis = self._task_mode == "vast" and self._config.run_analysis_after_trial
        if run_analysis and stop_ok:
            captured = (
                rec.db_path,
                rec.animal_id,
                rec.session_id,
                rec.trial,
                getattr(rec, "_video_path", None),
                self._config.run_phase or "habituation",
            )
        else:
            captured = None
        self._trial_recorder = None
        self._record_frame_index = 0

        # Start pipeline analysis in background if enabled and no worker already running
        if captured and self._analysis_worker is None and AnalysisWorker is not None:
            db_path, animal_id, session_id, trial, video_path, run_phase = captured
            self._analysis_worker = AnalysisWorker(
                db_path=db_path,
                animal_id=animal_id,
                session_id=session_id,
                trial=trial,
                video_path=video_path,
                run_phase=run_phase,
            )
            self._analysis_worker.finished.connect(
                self._on_analysis_finished,
                Qt.ConnectionType.QueuedConnection,
            )
            self._analysis_worker.start()
            self.statusBar().showMessage("Analyzing trial…")

    def _on_start_trial(self) -> None:
        if not self._dev_mode:
            if not self._is_video_available():
                self.statusBar().showMessage("Start camera before running trials.")
                return
            virtual_mode = (
                self._camera_source.currentText().startswith("Virtual")
                and self._is_video_available()
            )
            if (
                self._task_spec.requires_mc_connection
                and not self._is_mc_connected()
                and not virtual_mode
            ):
                self.statusBar().showMessage("Connect MC before running trials.")
                return
        self._apply_ui_to_config()
        sid = self._session_id_edit.text().strip()
        lookup_status: Optional[str] = None

        # In virtual mode, Start trial should restart playback from frame 0.
        if (
            self._camera_source.currentText().startswith("Virtual")
            and self._camera_controller is not None
        ):
            try:
                self._camera_controller.rewind()
                self._virtual_has_initial_frame = False
                self._virtual_cached_frame_raw = None
                self._virtual_cached_frame_index = None
            except Exception:
                # Best-effort only; if rewind fails, playback will continue from current position.
                pass

        # Optional legacy-exit seeding:
        # when session seed is "legacy" (-1) and we're in Virtual mode,
        # copy exit_x/exit_y from the original legacy H5 trial that corresponds
        # to the selected virtual video.
        if (
            self._task_mode == "vast"
            and (
            self._camera_source.currentText().startswith("Virtual")
            and self._config.session.seed == -1
            and self._virtual_video_path is not None
            )
        ):
            self._trial_controller.clear_legacy_exit_xy()
            try:
                parsed = parse_virtual_video_identity(self._virtual_video_path.stem)
                if parsed is not None:
                    animal_id, session_id, trial = parsed
                    explicit_legacy_db = (self._config.session.legacy_seed_db_path or "").strip()
                    if explicit_legacy_db:
                        candidates = [Path(explicit_legacy_db)]
                    else:
                        base_dir = self._virtual_video_path.parent.parent
                        h5_name = self._config.h5_filename or "trials.h5"
                        candidates = [
                            base_dir / h5_name,
                            base_dir / "trials.h5",
                        ]
                        if self._config.output_dir:
                            candidates.append(Path(self._config.output_dir) / h5_name)
                    legacy_db_path = next((p for p in candidates if p.exists()), None)
                    if legacy_db_path is not None:
                        with open_db(legacy_db_path, "r") as h5:
                            grp_path = f"/{animal_id}/{session_id}/{trial}"
                            if grp_path in h5:
                                g_trial = h5[grp_path]
                                if "exit_x" in g_trial.attrs and "exit_y" in g_trial.attrs:
                                    exit_x = float(g_trial.attrs["exit_x"])
                                    exit_y = float(g_trial.attrs["exit_y"])
                                    self._trial_controller.set_legacy_exit_xy(exit_x, exit_y)
                                    loaded_exit_idx = None
                                    for key_name in ("exit_angle_index", "exit_idx", "exit_index"):
                                        if key_name in g_trial.attrs:
                                            try:
                                                loaded_exit_idx = int(g_trial.attrs[key_name]) + 1
                                            except Exception:
                                                loaded_exit_idx = None
                                            break
                                    if loaded_exit_idx is not None:
                                        lookup_status = (
                                            f"Legacy exit lookup: loaded from {legacy_db_path} "
                                            f"(exit #{loaded_exit_idx})."
                                        )
                                    else:
                                        lookup_status = f"Legacy exit lookup: loaded from {legacy_db_path}."
                                else:
                                    lookup_status = "Legacy exit lookup: exit_x/exit_y missing; using computed exit."
                            else:
                                lookup_status = "Legacy exit lookup: trial not found; using computed exit."
                    else:
                        lookup_status = "Legacy exit lookup: H5 not found; using computed exit."
                else:
                    lookup_status = "Legacy exit lookup: couldn't parse video name; using computed exit."
            except Exception as e:
                lookup_status = f"Legacy exit lookup failed ({e}); using computed exit."

        msg = self._trial_controller.do_start(sid, lookup_status=lookup_status)
        self._apply_status_and_buttons()
        self.statusBar().showMessage(msg)
        if self._trial_controller.run_active:
            if self._run_timer is None or not self._run_timer.isActive():
                self._run_timer = QTimer(self)
                self._run_timer.timeout.connect(self._on_run_timer)
                self._run_timer.start(self._run_timer_interval_ms)
                self._run_timer_last_s = None
        else:
            if self._run_timer is not None and self._run_timer.isActive():
                self._run_timer.stop()
                self._run_timer = None
            self._run_timer_last_s = None

    def _on_previous_trial(self) -> None:
        if not self._dev_mode:
            if not self._is_video_available():
                self.statusBar().showMessage("Start camera before running trials.")
                return
            virtual_mode = (
                self._camera_source.currentText().startswith("Virtual")
                and self._is_video_available()
            )
            if (
                self._task_spec.requires_mc_connection
                and not self._is_mc_connected()
                and not virtual_mode
            ):
                self.statusBar().showMessage("Connect MC before running trials.")
                return
        sid = self._session_id_edit.text().strip()
        msg = self._trial_controller.do_previous(sid)
        self._apply_status_and_buttons()
        self.statusBar().showMessage(msg)

    def _on_next_trial(self) -> None:
        if not self._dev_mode:
            if not self._is_video_available():
                self.statusBar().showMessage("Start camera before running trials.")
                return
            virtual_mode = (
                self._camera_source.currentText().startswith("Virtual")
                and self._is_video_available()
            )
            if (
                self._task_spec.requires_mc_connection
                and not self._is_mc_connected()
                and not virtual_mode
            ):
                self.statusBar().showMessage("Connect MC before running trials.")
                return
        sid = self._session_id_edit.text().strip()
        msg = self._trial_controller.do_next(sid)
        self._apply_status_and_buttons()
        self.statusBar().showMessage(msg)

    def _on_session_controls_changed(self) -> None:
        """Sync phase, mode and session ID from UI; reset to first trial on any change."""
        sid = self._session_id_edit.text().strip()
        p = self._phase_combo.currentData()
        if p is not None and self._task_spec.set_phase_value is not None:
            self._task_spec.set_phase_value(self._config, str(p))
        m = self._mode_combo.currentData()
        if m is not None:
            self._task_spec.set_mode_value(self._config, str(m))
        self._trial_controller.apply_session_controls(sid)
        self._apply_status_and_buttons()

    def _apply_config_to_ui(self, gui: Optional[dict] = None) -> None:
        # Invalidate tracker cache so next frame uses updated config (e.g. fallback_tracking)
        if self._tracking_controller is not None:
            self._tracking_controller.set_config(self._config)
        phase_value = self._task_spec.get_phase_value(self._config)
        if self._task_spec.phase_options:
            idx = self._phase_combo.findData(phase_value)
            if idx >= 0:
                self._phase_combo.setCurrentIndex(idx)
            else:
                self._phase_combo.setCurrentIndex(0)
        mode_value = self._task_spec.get_mode_value(self._config)
        idx = self._mode_combo.findData(mode_value)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        else:
            self._mode_combo.setCurrentIndex(0)
        out = self._config.output_dir
        self._output_dir_edit.setText(out or "")
        self._h5_filename_edit.setText(self._config.h5_filename or "trials.h5")
        op = max(0, min(100, self._config.overlay_opacity_pct))
        self._track_opacity.setValue(op)
        self._track_opacity_label.setText(f"{op}%")
        self._run_analysis_after_trial_cb.setChecked(self._config.run_analysis_after_trial)
        if gui:
            self._apply_gui_dict_to_ui(gui)
        self._invalidate_tracker_cache()
        self._apply_status_and_buttons()

    def _apply_gui_dict_to_ui(self, gui: dict) -> None:
        """Restore GUI-only controls from a profile gui dict (and merge into config for tracking)."""
        if gui.get("track_show") is not None:
            self._config.track_show = bool(gui["track_show"])
        if gui.get("track_async") is not None:
            self._config.track_async = bool(gui["track_async"])
        if gui.get("track_backup_only") is not None:
            self._config.track_backup_only = bool(gui["track_backup_only"])
        if "track_sleap_path" in gui:
            self._config.sleap_model_path = str(gui.get("track_sleap_path") or "").strip()
        if gui.get("track_confidence") is not None:
            self._config.sleap_confidence_pct = max(0, min(100, int(gui["track_confidence"])))
        if gui.get("track_sleap_every_n") is not None:
            self._config.sleap_every_n = max(1, min(5, int(gui["track_sleap_every_n"])))
        if gui.get("track_opacity") is not None:
            v = max(0, min(100, int(gui["track_opacity"])))
            self._config.overlay_opacity_pct = v
            self._track_opacity.setValue(v)
            self._track_opacity_label.setText(f"{v}%")
        if gui.get("display_brightness") is not None:
            self._display_brightness.setValue(int(gui["display_brightness"]))
            self._display_brightness_label.setText(str(gui["display_brightness"]))
        if gui.get("display_contrast") is not None:
            v = max(50, min(200, int(gui["display_contrast"])))
            self._display_contrast.setValue(v)
            self._display_contrast_label.setText(f"{v}%")
        if gui.get("camera_flip") is not None:
            self._camera_flip.setChecked(bool(gui["camera_flip"]))
        if gui.get("camera_source") is not None:
            idx = self._camera_source.findText(str(gui["camera_source"]))
            if idx >= 0:
                self._camera_source.setCurrentIndex(idx)
        if gui.get("camera_device") is not None:
            self._camera_device.setValue(max(0, min(15, int(gui["camera_device"]))))
        if gui.get("arduino_port") is not None:
            port = str(gui["arduino_port"]).strip()
            if port and HAS_SERIAL and _list_ports is not None:
                idx = self._mc_port_combo.findData(port)
                if idx >= 0:
                    self._mc_port_combo.setCurrentIndex(idx)
                else:
                    self._mc_port_combo.addItem(port, port)
                    self._mc_port_combo.setCurrentIndex(self._mc_port_combo.count() - 1)

    def _apply_ui_to_config(self) -> None:
        p = self._phase_combo.currentData()
        if p is not None and self._task_spec.set_phase_value is not None:
            self._task_spec.set_phase_value(self._config, str(p))
        m = self._mode_combo.currentData()
        if m is not None:
            self._task_spec.set_mode_value(self._config, str(m))
        raw = self._output_dir_edit.text().strip()
        self._config.output_dir = raw if raw else None
        h5_raw = self._h5_filename_edit.text().strip()
        self._config.h5_filename = h5_raw if h5_raw else "trials.h5"
        self._config.overlay_opacity_pct = max(0, min(100, self._track_opacity.value()))
        self._config.run_analysis_after_trial = self._run_analysis_after_trial_cb.isChecked()

    def _read_reload_last_profile(self) -> bool:
        return read_reload_last_profile()

    def _save_last_profile_path(self) -> None:
        save_last_profile_path(self._profile_path)

    def _on_toggle_reload_last_profile(self) -> None:
        if not HAS_QT_SETTINGS:
            return
        write_reload_last_profile(self._reload_last_profile_action.isChecked())

    def _gui_log_error(self, message: str) -> None:
        """Append a message to the GUI error log (View error log) and to the rotating file log."""
        from datetime import datetime
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
            self._trial_controller.ensure_created(
                self._session_id_edit.text().strip(), 0
            )
            self._apply_status_and_buttons()
            return
        if not HAS_QT_SETTINGS:
            self._trial_controller.ensure_created(
                self._session_id_edit.text().strip(), 0
            )
            self._apply_status_and_buttons()
            return
        path = read_last_profile_path()
        if path and path.exists():
            try:
                self._config, session_id, ti, gui, slot = load_profile(path)
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
            except Exception:
                self._trial_controller.ensure_created(
                    self._session_id_edit.text().strip(), 0
                )
                self._apply_status_and_buttons()
        else:
            self._trial_controller.ensure_created(
                self._session_id_edit.text().strip(), 0
            )
            self._apply_status_and_buttons()

    def _on_load_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load profile", "", "JSON (*.json);;All (*)"
        )
        if path:
            try:
                self._config, session_id, ti, gui, slot = load_profile(Path(path))
                session_id_safe = sanitize_session_id(session_id) if session_id else ""
                self._profile_path = Path(path)
                self._apply_config_to_ui(gui=gui)
                dlg = getattr(self, "_settings_dialog", None)
                if dlg is not None and hasattr(dlg, "set_config"):
                    dlg.set_config(self._config)
                self._trial_controller = self._task_spec.controller_factory(self._config)
                self._trial_controller.add_state_listener(self._on_trial_state_change)
                self._trial_controller.reset(session_id_safe, ti, slot_idx=slot)
                if session_id_safe:
                    self._session_id_edit.setText(session_id_safe)
                self._update_window_title()
                self._save_last_profile_path()
                self._apply_status_and_buttons()
                self.statusBar().showMessage(f"Loaded {path}")
            except Exception as e:
                self.statusBar().showMessage(f"Load failed: {e}")

    def _on_save_profile(self) -> None:
        path = self._profile_path
        if not path:
            path_str, _ = QFileDialog.getSaveFileName(
                self, "Save profile", "", "JSON (*.json);;All (*)"
            )
            path = Path(path_str) if path_str else None
        if path:
            try:
                self._apply_ui_to_config()
                snapshot = self._trial_controller.get_session_snapshot()
                session_id, trial_idx, slot_idx = (snapshot if snapshot else (None, None, None))
                gui = gui_to_dict(
                    track_show=self._config.track_show,
                    track_async=self._config.track_async,
                    track_backup_only=self._config.track_backup_only,
                    track_sleap_path=self._config.sleap_model_path or "",
                    track_confidence=self._config.sleap_confidence_pct,
                    track_sleap_every_n=self._config.sleap_every_n,
                    track_opacity=self._track_opacity.value(),
                    display_brightness=self._display_brightness.value(),
                    display_contrast=self._display_contrast.value(),
                    camera_flip=self._camera_flip.isChecked(),
                    camera_source=self._camera_source.currentText(),
                    camera_device=self._camera_device.value(),
                    arduino_port=(self._mc_port_combo.currentData() or self._mc_port_combo.currentText() or "").strip(),
                )
                save_profile(self._config, path, session_id=session_id, trial_idx=trial_idx, slot_idx=slot_idx, gui=gui)
                self._profile_path = path
                self._update_window_title()
                self._save_last_profile_path()
                self.statusBar().showMessage(f"Saved {path}")
            except Exception as e:
                self.statusBar().showMessage(f"Save failed: {e}")

    def _on_stop(self) -> None:
        self._on_stop_run()
        self.statusBar().showMessage("Stopped.")

    def _on_run_exports(self) -> None:
        """Run VAST CSV exports on one or more databases."""
        if self._task_mode != "vast":
            self.statusBar().showMessage("Exports are only available for VAST right now.")
            return
        if not HAS_QT:
            return
        # Default selection: current controller output DB
        default_dir = self._config.output_dir or ""
        h5_name = (self._config.h5_filename or "trials.h5").strip() or "trials.h5"
        if Path(h5_name).name != h5_name:
            h5_name = Path(h5_name).name
        start_path = str(Path(default_dir) / h5_name) if default_dir else ""

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select VAST results H5 file(s)",
            start_path,
            "HDF5 (*.h5 *.hdf5);;All (*)",
        )
        if not paths:
            return

        # Choose output folder for combined exports
        out_dir_str = QFileDialog.getExistingDirectory(
            self,
            "Select output folder for combined exports",
            default_dir or "",
        )
        if not out_dir_str:
            return
        out_dir = Path(out_dir_str)

        from maze.pipeline.exports.csv_trials import export_all_for_dbs

        try:
            db_paths = [Path(p) for p in paths]
            export_all_for_dbs(
                db_paths=db_paths,
                output_dir=out_dir,
                include_mistrials=False,
            )
            self.statusBar().showMessage(f"Exports completed → {out_dir}")
        except Exception as e:
            self.statusBar().showMessage(f"Exports failed: {e}")

    def _on_open_current_db_h5web(self) -> None:
        """Open the current output H5 DB (output_dir + h5_filename) in h5web."""
        output_dir = self._config.output_dir
        if not output_dir:
            self.statusBar().showMessage("No output folder set.")
            return
        h5_name = (
            (self._config.h5_filename or "trials.h5").strip()
            or "trials.h5"
        )
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


def run_gui(
    debug_log: bool = False,
    dev: bool = False,
    *,
    task_mode: AcquisitionMode = "vast",
) -> int:
    from ..app_shell import run_mode_gui

    return run_mode_gui(task_mode, debug_log=debug_log, dev=dev)


def build_window(
    dev: bool = False,
    *,
    task_mode: AcquisitionMode = "vast",
) -> MainWindow:
    if not HAS_QT:
        raise RuntimeError(QT_ERROR_MESSAGE)
    return MainWindow(task_mode=task_mode, dev=dev)
