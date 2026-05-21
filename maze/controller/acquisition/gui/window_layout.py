"""Main window QWidget layout construction (Phase D4e)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

try:
    from ..arduino import ArduinoStimulus, HAS_SERIAL
except ImportError:
    ArduinoStimulus = None  # type: ignore[misc, assignment]
    HAS_SERIAL = False

try:
    from ..camera import HAS_CAMERA, HAS_VIMBA
except (ImportError, RuntimeError):
    HAS_CAMERA = False
    HAS_VIMBA = False

try:
    from .section_with_settings import SectionWithSettings
except ImportError:
    SectionWithSettings = None  # type: ignore[misc, assignment]

HAS_QT = True

if TYPE_CHECKING:
    from .main_window import MainWindow


def build_main_window_layout(window: MainWindow) -> None:
    """Create central widget, sections, and widget signal hooks (not menus)."""
    window._central = QWidget()
    window.setCentralWidget(window._central)
    layout = QVBoxLayout(window._central)

    # Camera preview
    camera_section = (
        SectionWithSettings("Camera", "Open Settings → Task")
        if SectionWithSettings
        else QGroupBox("Camera")
    )
    camera_ly = camera_section.content_layout() if SectionWithSettings else QVBoxLayout()
    if not SectionWithSettings:
        camera_section.setLayout(camera_ly)
    cam_row = QHBoxLayout()
    cam_row.addWidget(QLabel("Source:"))
    window._camera_source = QComboBox()
    window._camera_source.addItem("OpenCV")
    if HAS_VIMBA:
        window._camera_source.addItem("GigE (Vimba)")
    window._camera_source.addItem("Virtual (video file)")
    window._camera_source.setToolTip(
        "OpenCV = USB/DirectShow index. GigE = Allied Vision (e.g. Manta) via Vimba."
    )
    cam_row.addWidget(window._camera_source)
    cam_row.addWidget(QLabel("Device:"))
    window._camera_device = QSpinBox()
    window._camera_device.setRange(0, 15)
    window._camera_device.setValue(0)
    window._camera_device.setToolTip("OpenCV: index 0,1,… . GigE: device index (0=first).")
    cam_row.addWidget(window._camera_device)
    window._camera_start_btn = QPushButton("Start camera", clicked=window._on_start_camera)
    window._camera_stop_btn = QPushButton("Stop camera", clicked=window._on_stop_camera)
    window._camera_stop_btn.setEnabled(False)
    cam_row.addWidget(window._camera_start_btn)
    cam_row.addWidget(window._camera_stop_btn)
    window._camera_flip = QCheckBox("Flip image")
    cam_row.addWidget(window._camera_flip)
    camera_ly.addLayout(cam_row)
    # Display brightness/contrast (preview only)
    display_row = QHBoxLayout()
    display_row.addWidget(QLabel("Brightness:"))
    window._display_brightness = QSlider(Qt.Orientation.Horizontal)
    window._display_brightness.setRange(-100, 100)
    window._display_brightness.setValue(0)
    window._display_brightness.setToolTip("Display brightness offset (-100 to 100)")
    display_row.addWidget(window._display_brightness)
    window._display_brightness_label = QLabel("0")
    display_row.addWidget(window._display_brightness_label)
    display_row.addWidget(QLabel("Contrast:"))
    window._display_contrast = QSlider(Qt.Orientation.Horizontal)
    window._display_contrast.setRange(50, 200)
    window._display_contrast.setValue(100)
    window._display_contrast.setToolTip("Display contrast (50%–200%; 100% = no change)")
    display_row.addWidget(window._display_contrast)
    window._display_contrast_label = QLabel("100%")
    display_row.addWidget(window._display_contrast_label)
    display_row.addWidget(QLabel("Overlay opacity:"))
    window._track_opacity = QSlider(Qt.Orientation.Horizontal)
    window._track_opacity.setRange(0, 100)
    window._track_opacity.setValue(70)
    window._track_opacity.setToolTip("Tracking overlay opacity (0–100%).")
    display_row.addWidget(window._track_opacity)
    window._track_opacity_label = QLabel("70%")
    display_row.addWidget(window._track_opacity_label)
    camera_ly.addLayout(display_row)
    window._camera_label = QLabel()
    window._camera_label.setMinimumSize(320, 240)
    window._camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window._camera_label.setText("No camera" if not HAS_CAMERA else "Click Start camera")
    window._camera_label.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
    window._camera_label.setMouseTracking(True)
    camera_ly.addWidget(window._camera_label)
    # Preview click-to-set (arena center / RAM template / backup range) lives in Settings.
    arena_track_subrow = QHBoxLayout()
    arena_track_subrow.addWidget(QLabel("Gray (hover):"))
    window._intensity_hover_label = QLabel("—")
    window._intensity_hover_label.setMinimumWidth(36)
    window._intensity_hover_label.setToolTip(
        "Grayscale 0–255 under cursor (same as backup tracking). Move over live preview."
    )
    arena_track_subrow.addWidget(window._intensity_hover_label)
    arena_track_subrow.addStretch()

    # Video and frame indicators are moved to a third row
    arena_track_third_row = QHBoxLayout()
    arena_track_third_row.addWidget(QLabel("Tracking Source:"))
    window._track_source_label = QLabel("—")
    window._track_source_label.setToolTip("Current frame: SLEAP or Fallback")
    arena_track_third_row.addWidget(window._track_source_label)
    arena_track_third_row.addWidget(QLabel("Display FPS:"))
    window._track_display_fps_label = QLabel("—")
    window._track_display_fps_label.setToolTip("Preview frame rate")
    arena_track_third_row.addWidget(window._track_display_fps_label)
    arena_track_third_row.addWidget(QLabel("Video:"))
    window._video_filename_label = QLabel("—")
    window._video_filename_label.setToolTip("Current virtual video filename")
    arena_track_third_row.addWidget(window._video_filename_label)
    arena_track_third_row.addWidget(QLabel("Frame:"))
    window._frame_counter_label = QLabel("—")
    window._frame_counter_label.setToolTip("Virtual/preview frame index (and total if known)")
    arena_track_third_row.addWidget(window._frame_counter_label)
    arena_track_third_row.addStretch()

    camera_ly.addLayout(arena_track_subrow)
    camera_ly.addLayout(arena_track_third_row)
    window._virtual_scrub_row_w = QWidget()
    scrub_ly = QHBoxLayout(window._virtual_scrub_row_w)
    scrub_ly.setContentsMargins(0, 0, 0, 0)
    scrub_ly.addWidget(QLabel("Video position:"))
    window._virtual_scrub_slider = QSlider(Qt.Orientation.Horizontal)
    window._virtual_scrub_slider.setMinimum(0)
    window._virtual_scrub_slider.setMaximum(0)
    window._virtual_scrub_slider.valueChanged.connect(window._on_virtual_scrub_changed)
    scrub_ly.addWidget(window._virtual_scrub_slider)
    window._virtual_scrub_label = QLabel("0 / 0")
    scrub_ly.addWidget(window._virtual_scrub_label)
    window._virtual_scrub_row_w.setVisible(False)
    camera_ly.addWidget(window._virtual_scrub_row_w)
    layout.addWidget(camera_section)
    if SectionWithSettings:
        camera_section.settings_clicked.connect(lambda: window._on_open_settings_to_tab("task"))

    # MC (microcontroller) panel: COM port, Connect, status
    mc_section = QGroupBox("MC")
    mc_ly = QHBoxLayout()
    mc_section.setLayout(mc_ly)
    mc_ly.addWidget(QLabel("COM port:"))
    window._mc_port_combo = QComboBox()
    window._mc_port_combo.setMinimumWidth(180)
    window._mc_port_combo.setToolTip("Serial port for vibration controller (Arduino).")
    mc_ly.addWidget(window._mc_port_combo)
    window._mc_refresh_btn = QPushButton("Refresh", clicked=window._on_mc_refresh_ports)
    mc_ly.addWidget(window._mc_refresh_btn)
    window._mc_connect_btn = QPushButton("Connect", clicked=window._on_mc_connect)
    mc_ly.addWidget(window._mc_connect_btn)
    window._mc_flash_btn = QPushButton("Flash firmware", clicked=window._on_mc_flash)
    window._mc_flash_btn.setToolTip(
        "Compile and upload firmware via arduino-cli (dev only; run with -d/--dev)."
    )
    window._mc_flash_btn.setEnabled(window._dev_mode)
    mc_ly.addWidget(window._mc_flash_btn)
    window._mc_status_label = QLabel("Disconnected")
    window._mc_status_label.setStyleSheet("color: gray;")
    window._mc_status_label.setToolTip("MC connection status")
    mc_ly.addWidget(window._mc_status_label)
    mc_ly.addStretch()
    layout.addWidget(mc_section)
    if not HAS_SERIAL or ArduinoStimulus is None:
        window._mc_port_combo.setEnabled(False)
        window._mc_refresh_btn.setEnabled(False)
        window._mc_connect_btn.setEnabled(False)
        window._mc_flash_btn.setEnabled(False)
        window._mc_status_label.setText("pyserial required")
    else:
        window._on_mc_refresh_ports()

    # Output folder (main layout)
    out_section = (
        SectionWithSettings("Output", "Open Settings → Session")
        if SectionWithSettings
        else QGroupBox("Output")
    )
    out_ly = QHBoxLayout()
    if SectionWithSettings:
        out_section.content_layout().addLayout(out_ly)
    else:
        out_section.setLayout(out_ly)
    window._output_dir_edit = QLineEdit()
    window._output_dir_edit.setPlaceholderText(
        "Folder for H5 file; videos in <h5_stem>_vids subfolder"
    )
    out_ly.addWidget(window._output_dir_edit)
    window._output_browse_btn = QPushButton("Browse…", clicked=window._on_browse_output)
    out_ly.addWidget(window._output_browse_btn)
    layout.addWidget(out_section)
    if SectionWithSettings:
        out_section.settings_clicked.connect(lambda: window._on_open_settings_to_tab("session"))

    # Session controls (session ID, run mode)
    session_section = (
        SectionWithSettings("Session controls", "Open Settings → Session")
        if SectionWithSettings
        else QGroupBox("Session controls")
    )
    session_ly = QHBoxLayout()
    if SectionWithSettings:
        session_section.content_layout().addLayout(session_ly)
    else:
        session_section.setLayout(session_ly)
    out_ly.addWidget(QLabel("H5 file:"))
    window._h5_filename_edit = QLineEdit()
    window._h5_filename_edit.setPlaceholderText("trials.h5")
    window._h5_filename_edit.setToolTip("Filename for the H5 database in the output folder.")
    out_ly.addWidget(window._h5_filename_edit)
    session_ly.addWidget(QLabel("Session ID:"))
    window._session_id_edit = QLineEdit()
    window._session_id_edit.setPlaceholderText("e.g. 2025-02-19-A")
    window._session_id_edit.setToolTip(
        "Letters, digits, hyphen, period only (no underscore; used as delimiter in filenames)."
    )
    if HAS_QT:
        session_id_validator = QRegularExpressionValidator(
            QRegularExpression(r"^[a-zA-Z0-9.\-]*$")
        )
        window._session_id_edit.setValidator(session_id_validator)
    session_ly.addWidget(window._session_id_edit)
    window._phase_label = QLabel(window._task_spec.phase_label or "Phase:")
    session_ly.addWidget(window._phase_label)
    window._phase_combo = QComboBox()
    for label, value in window._task_spec.phase_options:
        window._phase_combo.addItem(label, value)
    session_ly.addWidget(window._phase_combo)
    session_ly.addWidget(QLabel("Mode:"))
    window._mode_combo = QComboBox()
    for label, value in window._task_spec.mode_options:
        window._mode_combo.addItem(label, value)
    session_ly.addWidget(window._mode_combo)
    show_phase = bool(window._task_spec.phase_options)
    window._phase_label.setVisible(show_phase)
    window._phase_combo.setVisible(show_phase)
    window._session_id_edit.textChanged.connect(window._on_session_controls_changed)
    window._phase_combo.currentIndexChanged.connect(window._on_session_controls_changed)
    window._mode_combo.currentIndexChanged.connect(window._on_session_controls_changed)
    window._h5_filename_edit.textChanged.connect(window._on_session_controls_changed)
    layout.addWidget(session_section)
    if SectionWithSettings:
        session_section.settings_clicked.connect(
            lambda: window._on_open_settings_to_tab("session")
        )

    # Status (state, trial, exit, animal, timers, duty)
    status_g = QGroupBox("Status")
    status_ly = QVBoxLayout()
    status_g.setLayout(status_ly)
    status_row1 = QHBoxLayout()
    status_row1.addWidget(QLabel("State:"))
    window._status_state = QLabel("—")
    status_row1.addWidget(window._status_state)
    status_row1.addWidget(QLabel("Animal ID:"))
    window._status_animal_id = QLabel("—")
    status_row1.addWidget(window._status_animal_id)
    status_row1.addWidget(QLabel("Trial:"))
    window._status_trial = QLabel("—")
    status_row1.addWidget(window._status_trial)
    # status_row2 = QHBoxLayout()
    status_row1.addWidget(QLabel(window._task_spec.exit_status_label))
    window._status_exit = QLabel("—")
    status_row1.addWidget(window._status_exit)
    status_row1.addWidget(QLabel("ITI:"))
    window._status_iti = QLabel("—")
    status_row1.addWidget(window._status_iti)
    status_row1.addWidget(QLabel("Trial timer:"))
    window._status_trial_timer = QLabel("—")
    status_row1.addWidget(window._status_trial_timer)
    status_row1.addWidget(QLabel("Duty %:"))
    window._status_duty = QLabel("—")
    window._status_duty.setToolTip(
        "Feedback intensity that would be written (from current position)"
    )
    status_row1.addWidget(window._status_duty)
    status_ly.addLayout(status_row1)
    # status_ly.addLayout(status_row2)
    layout.addWidget(status_g)

    # Run
    run_g = QGroupBox("Run")
    run_ly = QHBoxLayout()
    run_g.setLayout(run_ly)
    window._start_trial_btn = QPushButton("Start trial", clicked=window._on_start_trial)
    run_ly.addWidget(window._start_trial_btn)
    window._previous_trial_btn = QPushButton("Previous trial", clicked=window._on_previous_trial)
    run_ly.addWidget(window._previous_trial_btn)
    window._next_trial_btn = QPushButton("Next trial", clicked=window._on_next_trial)
    run_ly.addWidget(window._next_trial_btn)
    window._end_trial_btn = QPushButton("Manual Success", clicked=window._on_end_trial)
    window._end_trial_btn.setEnabled(False)
    run_ly.addWidget(window._end_trial_btn)
    window._stop_btn = QPushButton("Stop", clicked=window._on_stop)
    run_ly.addWidget(window._stop_btn)
    window._run_analysis_after_trial_cb = QCheckBox("Run analysis after each trial")
    window._run_analysis_after_trial_cb.setToolTip(
        "Run the maze pipeline (metrics, heatmap, movement bouts) when a trial ends. Requires maze.pipeline."
    )
    run_ly.addWidget(window._run_analysis_after_trial_cb)
    layout.addWidget(run_g)

    window._track_opacity.valueChanged.connect(window._on_track_opacity_changed)
    window._display_brightness.valueChanged.connect(window._on_display_brightness_changed)
    window._display_contrast.valueChanged.connect(window._on_display_contrast_changed)
    window._camera_label.installEventFilter(window)
    layout.addStretch()
