"""
Main controller GUI: profile, calibration, config, run, export.

Reference: VAST/legacy_sss.pdf for control layout inspiration.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, Tuple, Union

import numpy as np

from ..arena import distance_px, in_exit_zone
from ..config import ControllerConfig
from ..h5web_server import get_h5web_static_dir, run_server
from ..profile import load_profile, save_profile, gui_to_dict
from ..h5_writer import open_db
from ..recording import TrialRecorder
from .. import app_logging
from ..trial_logic import (
    OverlayInfo,
    Phase,
    TrialMode,
    TrialState,
    TrialController,
    parse_phase_mode_from_config,
)

# Session ID is used in file paths and H5 keys; restrict to filename-safe characters.
# Underscore is excluded because it is the delimiter in video names (animal_session_trial).
_SESSION_ID_ALLOWED_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
)


def _sanitize_session_id(value: str) -> str:
    """Return value with only filename-safe characters (for Session ID field)."""
    return "".join(c for c in value if c in _SESSION_ID_ALLOWED_CHARS)


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
    from PySide6.QtCore import Qt, QRegularExpression, QTimer, QEvent, QUrl, QSettings, QThread, Signal
    from PySide6.QtGui import QImage, QPixmap, QRegularExpressionValidator
    HAS_QT = True
except ImportError:
    HAS_QT = False

if HAS_QT:
    class AnalysisWorker(QThread):
        """Run VAST pipeline analysis for one trial in the background."""
        finished = Signal(bool, str)  # success, message

        def __init__(
            self,
            db_path: Path,
            animal_id: str,
            session_id: str,
            trial: str,
            video_path: Optional[Path],
            run_phase: str,
        ) -> None:
            super().__init__()
            self._db_path = db_path
            self._animal_id = animal_id
            self._session_id = session_id
            self._trial = trial
            self._video_path = video_path
            self._run_phase = run_phase

        def run(self) -> None:
            from ..post_trial_analysis import run_analysis_for_trial
            success, message = run_analysis_for_trial(
                db_path=self._db_path,
                animal_id=self._animal_id,
                session_id=self._session_id,
                trial=self._trial,
                video_path=self._video_path,
                run_phase=self._run_phase,
            )
            self.finished.emit(success, message)
else:
    AnalysisWorker = None  # type: ignore[misc, assignment]

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

_SETTINGS_ORG = "VAST"
_SETTINGS_APP = "Controller"
_KEY_RELOAD_LAST_PROFILE = "reload_last_profile"
_KEY_LAST_PROFILE_PATH = "last_profile_path"

def _frame_to_pixmap(img):
    """Convert OpenCV image (BGR (H,W,3) or gray (H,W)) to QPixmap. Keeps a copy for Qt."""
    if _cv2 is None or img is None:
        return None
    if img.ndim == 2:
        h, w = img.shape
        qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
    else:
        rgb = _cv2.cvtColor(img, _cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        qimg = QImage(rgb.data, w, h, w * c, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


def _apply_brightness_contrast(
    img: np.ndarray,
    brightness: int,
    contrast_pct: int,
) -> np.ndarray:
    """Apply display-only brightness (offset) and contrast (scale). Modifies a copy.
    brightness: -100..100 (added to pixel after contrast).
    contrast_pct: 50..200 (100 = no change; scale around 128).
    """
    if _cv2 is None or (brightness == 0 and contrast_pct == 100):
        return img
    out = img.astype(np.float64)
    scale = contrast_pct / 100.0
    out = (out - 128.0) * scale + 128.0 + float(brightness)
    out = np.clip(out, 0, 255).astype(np.uint8)
    return out


# Fore-nodes used for cyan "spot" marker (average position); names matched case-insensitively
_SPOT_FORE_NODES = frozenset({"forel", "forer", "nose", "neck"})


def _draw_roi_and_tracking_overlay(
    img: np.ndarray,
    roi_center_xy: Optional[Tuple[float, float]],
    roi_radius_px: float,
    track_xy: Optional[Tuple[float, float]],
    track_valid: bool,
    overlay_opacity: float,
    overlay_info: Optional[OverlayInfo] = None,
    track_source: str = "fallback",
    pose_xy: Optional[np.ndarray] = None,
    pose_scores: Optional[np.ndarray] = None,
    pose_edge_inds: Optional[list] = None,
    pose_node_names: Optional[list] = None,
    pose_node_valid: Optional[np.ndarray] = None,
    blob_mask: Optional[np.ndarray] = None,
    blob_crop_rect: Optional[Tuple[int, int, int, int]] = None,
) -> np.ndarray:
    """Draw ROI circle, state-dependent regions, and tracking (skeleton for SLEAP, spot, target marker + blob mask for fallback). Returns BGR.
    When blob_crop_rect (x0,y0,x1,y1) is set, blob_mask is in crop coords and we blend only in that slice (no full-frame alloc)."""
    if _cv2 is None:
        return img
    out = np.asarray(img, dtype=np.uint8).copy()
    if out.ndim == 2:
        out = _cv2.cvtColor(out, _cv2.COLOR_GRAY2BGR)
    elif out.ndim == 3 and out.shape[2] == 1:
        out = _cv2.cvtColor(out.squeeze(axis=2), _cv2.COLOR_GRAY2BGR)
    overlay = out.copy()
    cx_i = int(roi_center_xy[0]) if roi_center_xy else None
    cy_i = int(roi_center_xy[1]) if roi_center_xy else None
    # Arena (ROI) circle
    if roi_center_xy is not None and roi_radius_px > 0:
        _cv2.circle(overlay, (cx_i, cy_i), int(roi_radius_px), (0, 255, 255), 1)
    # State-dependent regions
    if overlay_info is not None and cx_i is not None and cy_i is not None:
        arena = overlay_info.arena
        state = overlay_info.state
        phase = overlay_info.phase
        show_center_edge = (
            state == TrialState.WAIT_NOT_CENTER
            or phase == Phase.HABITUATION
            or phase == Phase.HABITUATION_TRAINING
        )
        if show_center_edge and arena.center_radius_px > 0 and arena.radius_px > 0:
            _cv2.circle(
                overlay, (cx_i, cy_i), int(arena.center_radius_px), (255, 255, 0), 1
            )
        if state == TrialState.TRIAL_RUNNING and arena.px_per_cm > 0:
            ex_i = int(overlay_info.exit_x_px)
            ey_i = int(overlay_info.exit_y_px)
            exit_r_px = int(arena.exit_radius_cm * arena.px_per_cm)
            if exit_r_px > 0:
                _cv2.circle(overlay, (ex_i, ey_i), exit_r_px, (255, 0, 255), 2)
    # Tracking overlay: SLEAP = full skeleton (edges + nodes) + spot; fallback = green dot (same size as node)
    NODE_MARKER_R = 3  # radius for node circles and fallback dot; outline only (no fill)
    nose_color = (0, 128, 255)  # BGR green (nose / primary)
    non_nose_color = (0, 255, 255)  # BGR yellow
    spot_color = (255, 255, 0)  # BGR cyan
    if track_source == "sleap" and pose_xy is not None and pose_edge_inds:
        n_nodes = pose_xy.shape[0]
        node_valid = pose_node_valid if pose_node_valid is not None and pose_node_valid.shape == (n_nodes,) else np.ones(n_nodes, dtype=bool)
        # Skeleton edges (only between valid nodes)
        for (a, b) in pose_edge_inds:
            if a >= n_nodes or b >= n_nodes or not node_valid[a] or not node_valid[b]:
                continue
            xa, ya = float(pose_xy[a, 0]), float(pose_xy[a, 1])
            xb, yb = float(pose_xy[b, 0]), float(pose_xy[b, 1])
            if np.isfinite(xa) and np.isfinite(ya) and np.isfinite(xb) and np.isfinite(yb):
                pt_a = (int(round(xa)), int(round(ya)))
                pt_b = (int(round(xb)), int(round(yb)))
                _cv2.line(overlay, pt_a, pt_b, non_nose_color, 1, _cv2.LINE_AA)
        # Node circles: nose (index 0) = green, rest = yellow; only valid nodes; outline only
        for i in range(n_nodes):
            if not node_valid[i]:
                continue
            x, y = float(pose_xy[i, 0]), float(pose_xy[i, 1])
            if np.isfinite(x) and np.isfinite(y):
                pt = (int(round(x)), int(round(y)))
                color = nose_color if i == 0 else non_nose_color
                _cv2.circle(overlay, pt, NODE_MARKER_R, color, 1, _cv2.LINE_AA)
        # Cyan spot: average of valid fore-nodes (foreL, foreR, nose, neck)
        if pose_node_names is not None and len(pose_node_names) >= n_nodes:
            fore_inds = [i for i in range(n_nodes) if node_valid[i] and pose_node_names[i].strip().lower() in _SPOT_FORE_NODES]
            if fore_inds:
                pts = pose_xy[fore_inds]
                if np.all(np.isfinite(pts)):
                    sx = float(np.mean(pts[:, 0]))
                    sy = float(np.mean(pts[:, 1]))
                    _cv2.circle(overlay, (int(round(sx)), int(round(sy))), NODE_MARKER_R, spot_color, 1, _cv2.LINE_AA)
    # Fallback marker: green dot, same size as node markers, outline only (dim gray if invalid)
    if track_xy is not None:
        tx, ty = int(track_xy[0]), int(track_xy[1])
        color = (0, 255, 0) if track_valid else (128, 128, 128)  # BGR green vs dim gray
        _cv2.circle(overlay, (tx, ty), NODE_MARKER_R, color, 1, _cv2.LINE_AA)
    # Fallback blob mask overlay: semi-transparent green where blob was detected.
    # Use cv2.addWeighted + copyTo to avoid slow per-pixel fancy indexing (better FPS).
    if blob_mask is not None and blob_mask.ndim == 2:
        blob_alpha = 0.35
        green_bgr = (0, 255, 0)
        if blob_crop_rect is not None:
            x0, y0, x1, y1 = blob_crop_rect
            if x1 > x0 and y1 > y0 and blob_mask.shape == (y1 - y0, x1 - x0):
                overlay_slice = overlay[y0:y1, x0:x1]
                green_slice = np.empty_like(overlay_slice)
                green_slice[:] = green_bgr
                blended = _cv2.addWeighted(green_slice, blob_alpha, overlay_slice, 1.0 - blob_alpha, 0)
                _cv2.copyTo(blended, blob_mask, overlay_slice)
        elif blob_mask.shape[:2] == overlay.shape[:2]:
            green_layer = np.empty_like(overlay)
            green_layer[:] = green_bgr
            blended = _cv2.addWeighted(green_layer, blob_alpha, overlay, 1.0 - blob_alpha, 0)
            _cv2.copyTo(blended, blob_mask, overlay)
    alpha = max(0.0, min(1.0, overlay_opacity))
    _cv2.addWeighted(overlay, alpha, out, 1.0 - alpha, 0, out)
    return out


def export_trials_csv(db_path: Path, output_csv: Path) -> None:
    """Export trial list and paths to CSV. Supports new layout (animal_id/session_id/trial) and old (animal_id/phase/session/trial)."""
    import h5py
    rows = []
    with h5py.File(db_path, "r") as h5:
        for animal_id in h5.keys():
            if animal_id == "metadata":
                continue
            g_animal = h5[animal_id]
            if not hasattr(g_animal, "keys"):
                continue
            for level1 in g_animal.keys():
                g1 = g_animal[level1]
                if not hasattr(g1, "keys"):
                    continue
                # New layout: animal_id -> session_id -> trial (session group has run_mode attr)
                if hasattr(g1, "attrs") and "run_mode" in g1.attrs:
                    run_mode = str(g1.attrs.get("run_mode", ""))
                    for trial in g1.keys():
                        g_trial = g1[trial]
                        if hasattr(g_trial, "attrs"):
                            attrs = g_trial.attrs
                            rows.append({
                                "animal_id": animal_id,
                                "session_id": level1,
                                "trial": trial,
                                "run_mode": run_mode,
                                "video_path": attrs.get("video_path", ""),
                                "timestamp": attrs.get("timestamp", ""),
                            })
                    continue
                # Old layout: animal_id -> phase -> session -> trial
                for session in g1.keys():
                    g_session = g1[session]
                    if not hasattr(g_session, "keys"):
                        continue
                    for trial in g_session.keys():
                        g_trial = g_session[trial]
                        if hasattr(g_trial, "attrs"):
                            attrs = g_trial.attrs
                            rows.append({
                                "animal_id": animal_id,
                                "session_id": session,
                                "trial": trial,
                                "run_mode": "",
                                "video_path": attrs.get("video_path", ""),
                                "timestamp": attrs.get("timestamp", ""),
                            })
    if not rows:
        return
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["animal_id", "session_id", "trial", "run_mode", "video_path", "timestamp"],
        )
        w.writeheader()
        w.writerows(rows)


class MainWindow(QMainWindow):
    """Main window: profile, calibration, run, export."""

    def __init__(self, dev: bool = False) -> None:
        super().__init__()
        self._dev_mode = dev
        self._config = ControllerConfig()
        self._profile_path: Optional[Path] = None
        self._db_path: Optional[Path] = None
        self._update_window_title()
        self._camera_timer: Optional[QTimer] = None
        self._last_preview_img_size: Optional[Tuple[int, int]] = None  # (width, height) for click mapping
        self._last_track_xy: Optional[Tuple[float, float]] = None  # latest valid tracking position for run loop
        self._last_pose_xy: Optional[np.ndarray] = None  # (nodes, 2) for node max-jump invalidation; SLEAP only
        self._tracking_controller = TrackingController(self._config) if HAS_TRACKING and TrackingController is not None else None
        self._camera_controller = CameraController(self._config) if HAS_CAMERA else None
        self._display_fps_times: list = []  # ring of frame timestamps for display FPS (max 30)
        self._display_fps_max_samples = 30
        self._last_display_fps: float = 0.0  # latest preview FPS estimate for dev HUD
        self._last_frame_timings: Optional[Tuple[float, float]] = None  # (read_ms, process_ms) for tooltip
        self._gui_error_log: list = []  # list of timestamped error lines for View error log
        self._trial_controller = TrialController(self._config)
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
        camera_section = SectionWithSettings("Camera", "Open Settings → Arena") if SectionWithSettings else QGroupBox("Camera")
        camera_ly = camera_section.content_layout() if SectionWithSettings else QVBoxLayout()
        if not SectionWithSettings:
            camera_section.setLayout(camera_ly)
        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel("Source:"))
        self._camera_source = QComboBox()
        self._camera_source.addItem("OpenCV")
        if HAS_VIMBA:
            self._camera_source.addItem("GigE (Vimba)")
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
        self._roi_set_center_click = QCheckBox("Set arena center from next click on preview")
        arena_track_row.addWidget(self._roi_set_center_click)
        arena_track_row.addWidget(QLabel("Source:"))
        self._track_source_label = QLabel("—")
        self._track_source_label.setToolTip("Current frame: SLEAP or Fallback")
        arena_track_row.addWidget(self._track_source_label)
        arena_track_row.addWidget(QLabel("Display FPS:"))
        self._track_display_fps_label = QLabel("—")
        self._track_display_fps_label.setToolTip("Preview frame rate")
        arena_track_row.addWidget(self._track_display_fps_label)
        arena_track_row.addStretch()
        camera_ly.addLayout(arena_track_row)
        layout.addWidget(camera_section)
        if SectionWithSettings:
            camera_section.settings_clicked.connect(lambda: self._on_open_settings_to_tab(0))

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
            out_section.settings_clicked.connect(lambda: self._on_open_settings_to_tab(3))

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
        session_ly.addWidget(QLabel("Phase:"))
        self._phase_combo = QComboBox()
        for p in Phase:
            self._phase_combo.addItem(p.value.replace("_", " ").title(), p)
        session_ly.addWidget(self._phase_combo)
        session_ly.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        for m in TrialMode:
            self._mode_combo.addItem(m.value.replace("_", " ").title(), m)
        session_ly.addWidget(self._mode_combo)
        self._session_id_edit.textChanged.connect(self._on_session_controls_changed)
        self._phase_combo.currentIndexChanged.connect(self._on_session_controls_changed)
        self._mode_combo.currentIndexChanged.connect(self._on_session_controls_changed)
        self._h5_filename_edit.textChanged.connect(self._on_session_controls_changed)
        layout.addWidget(session_section)
        if SectionWithSettings:
            session_section.settings_clicked.connect(lambda: self._on_open_settings_to_tab(3))

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
        status_row1.addWidget(QLabel("Exit #:"))
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
            "Run VAST pipeline (metrics, heatmap, movement bouts) when a trial ends. Requires vast.pipeline."
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
        if self._profile_path:
            self.setWindowTitle(f"VAST Controller — {self._profile_path}")
        else:
            self.setWindowTitle("VAST Controller — Unsaved")

    def _on_track_opacity_changed(self, value: int) -> None:
        self._track_opacity_label.setText(f"{value}%")

    def _invalidate_tracker_cache(self) -> None:
        self._last_pose_xy = None  # node count may change with different model
        if self._tracking_controller is not None:
            path = self._config.sleap_model_path or ""
            backup_only = self._config.track_backup_only
            self._tracking_controller.set_sleap_params(path.strip(), backup_only)

    def _update_pose_last_and_valid(
        self, pose_xy: Optional[np.ndarray], node_max_jump_px: float
    ) -> Optional[np.ndarray]:
        """Update _last_pose_xy from pose_xy; return node_valid (True where node is finite and within max jump)."""
        if pose_xy is None or pose_xy.shape[0] == 0:
            return None
        n = pose_xy.shape[0]
        finite = np.isfinite(pose_xy).all(axis=1)
        if self._last_pose_xy is None or self._last_pose_xy.shape[0] != n:
            self._last_pose_xy = np.asarray(pose_xy, dtype=np.float64)
            return finite
        node_valid = finite.copy()
        if node_max_jump_px > 0:
            for i in range(n):
                if not finite[i]:
                    node_valid[i] = False
                    continue
                dx = float(pose_xy[i, 0]) - float(self._last_pose_xy[i, 0])
                dy = float(pose_xy[i, 1]) - float(self._last_pose_xy[i, 1])
                if (dx * dx + dy * dy) ** 0.5 > node_max_jump_px:
                    node_valid[i] = False
                    continue
                self._last_pose_xy[i, 0] = float(pose_xy[i, 0])
                self._last_pose_xy[i, 1] = float(pose_xy[i, 1])
        else:
            self._last_pose_xy = np.asarray(pose_xy, dtype=np.float64)
        return node_valid

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
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        self._reload_last_profile_action = file_menu.addAction(
            "Reload last profile on startup"
        )
        self._reload_last_profile_action.setCheckable(True)
        self._reload_last_profile_action.setChecked(self._read_reload_last_profile())
        self._reload_last_profile_action.triggered.connect(self._on_toggle_reload_last_profile)
        file_menu.addSeparator()
        file_menu.addAction("Load profile…", self._on_load_profile)
        file_menu.addAction("Save profile", self._on_save_profile)
        file_menu.addAction("Save profile as…", self._on_save_profile_as)
        file_menu.addAction("Open profile in editor", self._on_open_profile_in_editor)
        file_menu.addAction("Reload profile", self._on_reload_profile)
        file_menu.addSeparator()
        file_menu.addAction("Run exports…", self._on_run_exports)
        file_menu.addAction("Open current DB in h5web", self._on_open_current_db_h5web)
        file_menu.addAction("Open H5 in h5web…", self._on_open_h5web)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self._on_file_exit)
        settings_menu = menubar.addMenu("&Settings")
        settings_menu.addAction("Settings…", self._on_settings)
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("View error log", self._on_view_error_log)
        help_menu.addAction("Open log folder", self._on_open_log_folder)

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
            session_id_safe = _sanitize_session_id(session_id) if session_id else ""
            self._apply_config_to_ui(gui=gui)
            self._trial_controller = TrialController(self._config)
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

    _SETTINGS_TAB_NAMES = (
        "Arena", "Exit angles", "Stimulus", "Session",
        "Animals", "Tracking",
    )

    def _on_settings(self) -> None:
        if not HAS_SETTINGS_DIALOG or SettingsDialog is None:
            self.statusBar().showMessage("Settings dialog unavailable.")
            return
        dlg = getattr(self, "_settings_dialog", None)
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            return
        dlg = SettingsDialog(self._config, self, initial_tab_index=None)
        self._settings_dialog = dlg
        dlg.accepted.connect(lambda: self.statusBar().showMessage("Settings applied."))
        dlg.show()
        dlg.raise_()

    def _on_open_settings_to_tab(self, tab_index: int) -> None:
        if not HAS_SETTINGS_DIALOG or SettingsDialog is None:
            self.statusBar().showMessage("Settings dialog unavailable.")
            return
        dlg = getattr(self, "_settings_dialog", None)
        if dlg is None:
            dlg = SettingsDialog(self._config, self, initial_tab_index=tab_index)
            self._settings_dialog = dlg
            dlg.accepted.connect(lambda: (self._apply_config_to_ui(), self.statusBar().showMessage("Settings applied.")))
        else:
            dlg.set_current_tab(tab_index)
        tab_name = self._SETTINGS_TAB_NAMES[tab_index] if 0 <= tab_index < len(self._SETTINGS_TAB_NAMES) else "Settings"
        self.statusBar().showMessage(f"Settings → {tab_name}")
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_analysis_finished(self, success: bool, message: str) -> None:
        self._analysis_worker = None
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
                        self._config.arena.arena_center_x_px = float(ix)
                        self._config.arena.arena_center_y_px = float(iy)
                        self._roi_set_center_click.setChecked(False)
                        self.statusBar().showMessage(f"Arena center set to ({ix}, {iy})")
        return super().eventFilter(obj, event)

    def _on_camera_tick(self) -> None:
        if self._camera_controller is None:
            return
        t0 = time.perf_counter()
        img_raw = self._camera_controller.grab_frame()
        t1 = time.perf_counter()
        if img_raw is not None:
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
            # Raw frame for inference (no brightness/contrast); display uses a copy with adjustments
            if self._camera_flip.isChecked() and _cv2 is not None:
                img_raw = _cv2.flip(img_raw, 1)  # 1 = horizontal (flip x-axis)
            h, w = img_raw.shape[0], img_raw.shape[1]
            self._last_preview_img_size = (w, h)
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
            else:
                # show_track is False: no tracking overlay
                self._track_source_label.setText("—")
            opacity = self._track_opacity.value() / 100.0
            if show_track or (roi_center is not None and roi_r > 0):
                ft = self._config.fallback_tracking
                node_max_jump_px = ft.node_max_jump_px
                pose_node_valid = self._update_pose_last_and_valid(pose_xy, node_max_jump_px)
                # Combine confidence-based validity (from tracker) with jump-based validity
                if (
                    pose_node_valid_from_res is not None
                    and pose_xy is not None
                    and pose_node_valid_from_res.shape == (pose_xy.shape[0],)
                    and pose_node_valid is not None
                    and pose_node_valid.shape == pose_node_valid_from_res.shape
                ):
                    pose_node_valid = pose_node_valid & pose_node_valid_from_res
                img_display = _draw_roi_and_tracking_overlay(
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
            tc = self._trial_controller
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
                dist_to_exit_px = distance_px(x_px, y_px, exit_x, exit_y)
                in_exit = in_exit_zone(x_px, y_px, exit_x, exit_y, self._config.arena)
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

            pix = _frame_to_pixmap(img_display)
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
        try:
            if self._camera_controller is not None:
                device_index = self._camera_device.value()
                self._camera_controller.open(source, device_index)
                # Status message: keep simple for now; detailed backend info can
                # be added via CameraController hooks in the future.
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
        self._apply_status_and_buttons()

    def _on_mc_refresh_ports(self) -> None:
        """Repopulate COM port combo from serial.tools.list_ports."""
        if _list_ports is None:
            return
        current = self._mc_port_combo.currentData() or self._mc_port_combo.currentText()
        self._mc_port_combo.clear()
        self._mc_port_combo.addItem("— Select port —", "")
        for port in _list_ports.comports():
            label = f"{port.device}" + (f" ({port.description})" if port.description else "")
            self._mc_port_combo.addItem(label, port.device)
        idx = self._mc_port_combo.findData(current)
        if idx >= 0:
            self._mc_port_combo.setCurrentIndex(idx)
        elif current:
            self._mc_port_combo.addItem(current, current)
            self._mc_port_combo.setCurrentIndex(self._mc_port_combo.count() - 1)

    def _on_mc_connect(self) -> None:
        """Toggle MC connection: connect if disconnected, disconnect if connected."""
        if self._arduino_stimulus is not None and self._arduino_stimulus.connected:
            self._arduino_stimulus.disconnect()
            self._mc_connect_btn.setText("Connect")
            self._mc_status_label.setText("Disconnected")
            self._mc_status_label.setStyleSheet("color: gray;")
            self.statusBar().showMessage("MC disconnected.")
            self._apply_status_and_buttons()
            return
        port = self._mc_port_combo.currentData() or (self._mc_port_combo.currentText().strip() or None)
        if not port or port == "— Select port —":
            self.statusBar().showMessage("Select a COM port.")
            return
        s = self._config.stimulus
        try:
            self._arduino_stimulus = ArduinoStimulus(
                port=port,
                baud=9600,
                min_duty_pct=s.min_duty_pct,
                max_duty_pct=s.max_duty_pct,
            )
            if self._arduino_stimulus.connect(port):
                self._config.arduino_port = port
                self._mc_connect_btn.setText("Disconnect")
                self._mc_status_label.setText("Connected")
                self._mc_status_label.setStyleSheet("color: green;")
                self.statusBar().showMessage(f"MC connected on {port}")
                self._apply_status_and_buttons()
            else:
                self._arduino_stimulus = None
                self.statusBar().showMessage(
                    "Wrong firmware or no response. Load firmware/vast_controller_duty.ino on the MC."
                )
        except Exception as e:
            self._arduino_stimulus = None
            self.statusBar().showMessage(f"MC connect failed: {e}")

    def _on_mc_flash(self) -> None:
        """Compile and upload firmware via arduino-cli (dev only)."""
        if not self._dev_mode:
            return
        cli = shutil.which("arduino-cli")
        if not cli:
            QMessageBox.warning(
                self,
                "Flash firmware",
                "arduino-cli not found. Install from https://arduino.github.io/arduino-cli/ and add it to PATH.",
            )
            return
        port = (self._mc_port_combo.currentData() or self._mc_port_combo.currentText() or "").strip()
        if not port or port == "— Select port —":
            self.statusBar().showMessage("Select a COM port first.")
            QMessageBox.warning(self, "Flash firmware", "Select a COM port first.")
            return
        # Sketch dir: firmware/vast_controller_duty/ (folder name must match .ino for arduino-cli)
        try:
            firmware_dir = Path(__file__).resolve().parent.parent.parent / "firmware" / "vast_controller_duty"
        except Exception:
            firmware_dir = None
        if not firmware_dir or not firmware_dir.is_dir() or not (firmware_dir / "vast_controller_duty.ino").exists():
            QMessageBox.warning(
                self,
                "Flash firmware",
                f"Firmware folder not found (expected {firmware_dir} with vast_controller_duty.ino).",
            )
            return
        fqbn = "arduino:avr:uno"
        self.statusBar().showMessage("Compiling firmware…")
        try:
            r = subprocess.run(
                [cli, "compile", "--fqbn", fqbn, str(firmware_dir)],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            self.statusBar().showMessage("Compile timed out.")
            QMessageBox.warning(self, "Flash firmware", "Compile timed out (120 s).")
            return
        except Exception as e:
            self.statusBar().showMessage(f"Compile failed: {e}")
            QMessageBox.warning(self, "Flash firmware", f"Compile failed: {e}")
            return
        if r.returncode != 0:
            self.statusBar().showMessage("Compile failed.")
            out = (r.stdout or "") + (r.stderr or "")
            QMessageBox.warning(
                self,
                "Flash firmware",
                "Compile failed.\n\n" + (out.strip() or "No output"),
            )
            return
        self.statusBar().showMessage("Uploading firmware…")
        try:
            r = subprocess.run(
                [cli, "upload", "-p", port, "--fqbn", fqbn, str(firmware_dir)],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            self.statusBar().showMessage("Upload timed out.")
            QMessageBox.warning(self, "Flash firmware", "Upload timed out (60 s).")
            return
        except Exception as e:
            self.statusBar().showMessage(f"Upload failed: {e}")
            QMessageBox.warning(self, "Flash firmware", f"Upload failed: {e}")
            return
        if r.returncode != 0:
            self.statusBar().showMessage("Upload failed.")
            out = (r.stdout or "") + (r.stderr or "")
            QMessageBox.warning(
                self,
                "Flash firmware",
                "Upload failed.\n\n" + (out.strip() or "No output"),
            )
            return
        self.statusBar().showMessage(f"Firmware flashed to {port}. Reconnect to use.")
        QMessageBox.information(
            self,
            "Flash firmware",
            f"Firmware uploaded to {port}. Disconnect and reconnect the MC to use the new firmware.",
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
            self._session_id_edit.setText(_sanitize_session_id(str(d.get("session_id", ""))))
        bs = self._trial_controller.get_button_states()
        video_ok = self._is_video_available()
        mc_ok = self._is_mc_connected()
        # In dev mode, camera and MC are not required for run buttons
        run_ok = self._dev_mode or (video_ok and mc_ok)
        self._start_trial_btn.setEnabled(bs["start"] and run_ok)
        self._previous_trial_btn.setEnabled(bs["previous"] and run_ok)
        self._next_trial_btn.setEnabled(bs["next"] and run_ok)
        self._end_trial_btn.setEnabled(bs["end_trial"] and run_ok)
        self._stop_btn.setEnabled(bs["stop"] and run_ok)

    def _on_run_timer(self) -> None:
        now = time.monotonic()
        if self._run_timer_last_s is None:
            self._run_timer_last_s = now
            self._apply_status_and_buttons()
            return
        dt = now - self._run_timer_last_s
        self._run_timer_last_s = now
        x, y = self._last_track_xy if self._last_track_xy else (0.0, 0.0)
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

    def _on_trial_state_change(self, new_state: TrialState) -> None:
        """When trial ends (SUCCESS or TIMEOUT), advance slot first (so motors stop), then flush/clear recorder (may show duplicate popup)."""
        if new_state not in (TrialState.TRIAL_SUCCESS, TrialState.TRIAL_TIMEOUT):
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
            suffix = _next_keep_both_suffix(
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
        run_analysis = self._config.run_analysis_after_trial
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
            self._analysis_worker.finished.connect(self._on_analysis_finished)
            self._analysis_worker.start()
            self.statusBar().showMessage("Analyzing trial…")

    def _on_start_trial(self) -> None:
        if not self._dev_mode:
            if not self._is_video_available():
                self.statusBar().showMessage("Start camera before running trials.")
                return
            if not self._is_mc_connected():
                self.statusBar().showMessage("Connect MC before running trials.")
                return
        self._apply_ui_to_config()
        sid = self._session_id_edit.text().strip()
        msg = self._trial_controller.do_start(sid)
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
            if not self._is_mc_connected():
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
            if not self._is_mc_connected():
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
        if p is not None:
            self._config.run_phase = p.value
        m = self._mode_combo.currentData()
        if m is not None:
            self._config.run_mode = m.value
        self._trial_controller.apply_session_controls(sid)
        self._apply_status_and_buttons()

    def _apply_config_to_ui(self, gui: Optional[dict] = None) -> None:
        # Invalidate tracker cache so next frame uses updated config (e.g. fallback_tracking)
        if self._tracking_controller is not None:
            self._tracking_controller.set_config(self._config)
        phase_enum, mode_enum = parse_phase_mode_from_config(self._config)
        idx = self._phase_combo.findData(phase_enum)
        if idx >= 0:
            self._phase_combo.setCurrentIndex(idx)
        else:
            self._phase_combo.setCurrentIndex(0)
        idx = self._mode_combo.findData(mode_enum)
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
        if p is not None:
            self._config.run_phase = p.value
        m = self._mode_combo.currentData()
        if m is not None:
            self._config.run_mode = m.value
        raw = self._output_dir_edit.text().strip()
        self._config.output_dir = raw if raw else None
        h5_raw = self._h5_filename_edit.text().strip()
        self._config.h5_filename = h5_raw if h5_raw else "trials.h5"
        self._config.overlay_opacity_pct = max(0, min(100, self._track_opacity.value()))
        self._config.run_analysis_after_trial = self._run_analysis_after_trial_cb.isChecked()

    def _read_reload_last_profile(self) -> bool:
        if not HAS_QT:
            return True
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        return s.value(_KEY_RELOAD_LAST_PROFILE, True, type=bool)

    def _save_last_profile_path(self) -> None:
        if not HAS_QT or not self._profile_path:
            return
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue(_KEY_LAST_PROFILE_PATH, str(self._profile_path))

    def _on_toggle_reload_last_profile(self) -> None:
        if not HAS_QT:
            return
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue(_KEY_RELOAD_LAST_PROFILE, self._reload_last_profile_action.isChecked())

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
        if not self._read_reload_last_profile():
            self._trial_controller.ensure_created(
                self._session_id_edit.text().strip(), 0
            )
            self._apply_status_and_buttons()
            return
        if not HAS_QT:
            self._trial_controller.ensure_created(
                self._session_id_edit.text().strip(), 0
            )
            self._apply_status_and_buttons()
            return
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        path_str = s.value(_KEY_LAST_PROFILE_PATH, "", type=str)
        path = Path(path_str) if path_str else None
        if path and path.exists():
            try:
                self._config, session_id, ti, gui, slot = load_profile(path)
                session_id_safe = _sanitize_session_id(session_id) if session_id else ""
                self._profile_path = path
                self._apply_config_to_ui(gui=gui)
                self._trial_controller = TrialController(self._config)
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
                session_id_safe = _sanitize_session_id(session_id) if session_id else ""
                self._profile_path = Path(path)
                self._apply_config_to_ui(gui=gui)
                self._trial_controller = TrialController(self._config)
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

        from vast.pipeline.exports.csv_trials import export_all_for_dbs

        try:
            db_paths = [Path(p) for p in paths]
            exports = export_all_for_dbs(db_paths=db_paths, output_dir=out_dir, include_mistrials=False)
            self.statusBar().showMessage(f"Exports completed → {out_dir}")
        except Exception as e:
            self.statusBar().showMessage(f"Exports failed: {e}")

    def _launch_h5web_for_path(self, h5_path: Path) -> None:
        """Start h5web server and open browser for the given H5 file."""
        if not h5_path.exists():
            self.statusBar().showMessage(f"File not found: {h5_path}")
            return
        static_dir = get_h5web_static_dir()
        if static_dir is None:
            self.statusBar().showMessage(
                "h5web viewer not found (run: cd web/h5web && npm run build)"
            )
            return
        try:
            port, _ = run_server(h5_path, static_dir)
            url = f"http://127.0.0.1:{port}/?file={h5_path.name}"
            time.sleep(0.4)  # give server time to bind before opening browser
            webbrowser.open(url)
            self.statusBar().showMessage("Launched h5web")
        except Exception as e:
            self.statusBar().showMessage(f"Could not launch h5web: {e}")

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
        self._launch_h5web_for_path(db_path)

    def _on_open_h5web(self) -> None:
        """Open a user-selected H5 file in h5web."""
        h5_path_str, _ = QFileDialog.getOpenFileName(
            self, "Select H5 file", "", "HDF5 (*.h5 *.hdf5);;All (*)"
        )
        if not h5_path_str:
            return
        self._launch_h5web_for_path(Path(h5_path_str))


def _next_keep_both_suffix(
    db_path: Path,
    output_dir: Path,
    animal_id: str,
    session_id: str,
    trial: str,
) -> str:
    """Return the next available (n) suffix for Keep both: (2), (3), ... so that both H5 group and video path are free."""
    n = 2
    while True:
        suffix = f"({n})"
        h5_key = f"/{animal_id}/{session_id}/{trial}{suffix}"
        video_path = output_dir / f"{animal_id}_{session_id}_{trial}{suffix}.mp4"
        h5_exists = False
        if db_path.exists():
            try:
                with open_db(db_path, "r") as h5:
                    h5_exists = h5_key in h5
            except Exception:
                pass
        if not h5_exists and not video_path.exists():
            return suffix
        n += 1


def ask_trial_overwrite_merged(
    parent: QWidget,
    h5_key: Optional[str],
    video_path: Optional[Path],
    new_h5_key_with_suffix: Optional[str],
    new_video_path_with_suffix: Optional[Path],
    keep_both_suffix: str = "(2)",
) -> Union[Literal["overwrite"], Literal["discard"], Tuple[Literal["keep_both"], str]]:
    """
    Single dialog when trial data (H5) and/or video file already exist.
    h5_key: existing H5 group path (e.g. /animal/session/trial) or None if no conflict.
    video_path: existing video file path or None if no conflict.
    new_*_with_suffix: what will be used if user chooses Keep both.
    keep_both_suffix: suffix to return for Keep both (e.g. "(2)", "(3)"); should match the new_* paths.
    Returns overwrite, discard, or (keep_both, keep_both_suffix). Shows a warning if only one of H5/video is a duplicate.
    """
    if not HAS_QT:
        return "discard"
    has_h5 = h5_key is not None
    has_video = video_path is not None
    only_one = has_h5 != has_video

    parts = []
    if has_h5:
        parts.append(f"Trial data (H5) already exists at:\n  {h5_key}")
    if has_video:
        parts.append(f"Video file already exists at:\n  {video_path}")
    parts.append("")
    if only_one:
        parts.append(
            "Note: Only one of trial data or video file already exists. This is unusual."
        )
        parts.append("")
    parts.append("If you choose Keep both, the new trial will use:")
    if new_h5_key_with_suffix:
        parts.append(f"  H5 group: {new_h5_key_with_suffix}")
    if new_video_path_with_suffix:
        parts.append(f"  Video file: {new_video_path_with_suffix}")
    parts.append("")
    parts.append("Overwrite existing, discard this trial, or keep both?")

    box = QMessageBox(parent)
    box.setWindowTitle("Trial / video already exists")
    box.setText("\n".join(parts))
    overwrite_btn = box.addButton("Overwrite", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Discard", QMessageBox.ButtonRole.RejectRole)
    keep_btn = box.addButton("Keep both", QMessageBox.ButtonRole.ActionRole)
    box.exec()
    clicked = box.clickedButton()
    if clicked == overwrite_btn:
        return "overwrite"
    if clicked == keep_btn:
        return ("keep_both", keep_both_suffix)
    return "discard"


def run_gui(debug_log: bool = False, dev: bool = False) -> int:
    if not HAS_QT:
        print("PySide6 is required for the GUI. Install with: pip install PySide6")
        return 1
    app_logging.init_app_logging(debug_log=debug_log)
    app = QApplication(sys.argv)
    win = MainWindow(dev=dev)
    win.resize(500, 400)
    win.show()
    return app.exec()
