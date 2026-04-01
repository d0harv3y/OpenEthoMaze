"""
Settings dialog: all config fields in tabs (Arena, Exit angles, Stimulus, Session, Animals, Tracking). Session tab includes Session ID, Phase, Mode. Habituation settings live in Stimulus tab.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from ..config import ControllerConfig, AnimalInfo, FallbackTrackingConfig, FT_TO_CM, M_TO_CM
from ..trial_logic import Phase, TrialMode

try:
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QPushButton,
        QDoubleSpinBox,
        QSpinBox,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt, QRegularExpression, QSettings
    from PySide6.QtGui import QCloseEvent, QRegularExpressionValidator
    HAS_QT = True
except ImportError:
    # If PySide6 is unavailable or incomplete, fail the import cleanly so
    # the main window can treat SettingsDialog as unavailable.
    HAS_QT = False
    QCloseEvent = None
    raise

_SETTINGS_ORG = "VAST"
_SETTINGS_APP = "Controller"
_KEY_LAST_SETTINGS_TAB = "last_settings_tab"


def _parse_seed(text: str) -> Tuple[Optional[int], Optional[str]]:
    s = (text or "").strip()
    if not s:
        return (None, None)
    # Legacy sentinel:
    # - `seed == -1` means "use exit_x/exit_y from the original legacy trial"
    #   (primarily for Virtual acquisition + replay matching).
    if s.lower() == "legacy":
        return (-1, None)
    try:
        return (int(s), None)
    except ValueError:
        # Treat any non-integer value as explicit legacy DB path and enable legacy mode.
        return (-1, str(Path(s)))


class SettingsDialog(QDialog):
    """Settings window: modeless so you can use main window while it's open. Apply writes config and keeps dialog open."""

    def __init__(
        self,
        config: ControllerConfig,
        parent: Optional[QWidget] = None,
        initial_tab_index: Optional[int] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Settings")
        self.setWindowModality(Qt.WindowModality.NonModal)
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._arena_tab(), "Arena")
        self._tabs.addTab(self._exit_angles_tab(), "Exit angles")
        self._tabs.addTab(self._stimulus_tab(), "Stimulus")
        self._tabs.addTab(self._session_tab(), "Session")
        self._tabs.addTab(self._animals_tab(), "Animals")
        self._tabs.addTab(self._tracking_tab(), "Tracking")
        layout.addWidget(self._tabs)
        if initial_tab_index is not None and 0 <= initial_tab_index < self._tabs.count():
            self._tabs.setCurrentIndex(initial_tab_index)
        else:
            s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
            last = s.value(_KEY_LAST_SETTINGS_TAB, 0, type=int)
            if 0 <= last < self._tabs.count():
                self._tabs.setCurrentIndex(last)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        apply_btn = bbox.button(QDialogButtonBox.StandardButton.Apply)
        apply_btn.clicked.connect(self._on_apply)
        apply_btn.setDefault(True)
        apply_btn.setAutoDefault(True)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)
        self._fill_from_config()

    def set_current_tab(self, index: int) -> None:
        """Switch to the given settings tab (0-based). No-op if index out of range."""
        if 0 <= index < self._tabs.count():
            self._tabs.setCurrentIndex(index)

    def set_config(self, config: ControllerConfig) -> None:
        """Replace the backing config object and immediately refresh all fields."""
        self._config = config
        self._fill_from_config()

    def refresh_from_config(self) -> None:
        """Refresh widgets from the current backing config object."""
        self._fill_from_config()

    def _on_tab_changed(self, index: int) -> None:
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue(_KEY_LAST_SETTINGS_TAB, index)

    def _save_last_tab(self) -> None:
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue(_KEY_LAST_SETTINGS_TAB, self._tabs.currentIndex())

    def _arena_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        diameter_row = QHBoxLayout()
        self._arena_diameter_value = QDoubleSpinBox()
        self._arena_diameter_value.setRange(0.01, 50.0)
        self._arena_diameter_value.setDecimals(3)
        diameter_row.addWidget(self._arena_diameter_value)
        self._arena_diameter_unit = QComboBox()
        self._arena_diameter_unit.addItem("ft", "ft")
        self._arena_diameter_unit.addItem("m", "m")
        diameter_row.addWidget(self._arena_diameter_unit)
        f.addRow("Arena diameter:", diameter_row)
        self._arena_center_pct = QDoubleSpinBox()
        self._arena_center_pct.setRange(0.1, 1.0)
        self._arena_center_pct.setSingleStep(0.1)
        f.addRow("Center % (0–1):", self._arena_center_pct)
        self._arena_radius_px = QSpinBox()
        self._arena_radius_px.setRange(10, 9999)
        f.addRow("Arena ROI radius (px):", self._arena_radius_px)
        self._arena_tracking_radius_px = QSpinBox()
        self._arena_tracking_radius_px.setRange(0, 9999)
        self._arena_tracking_radius_px.setSpecialValueText("1.2× ROI (default)")
        self._arena_tracking_radius_px.setToolTip(
            "Radius of image region used for tracking. 0 = 1.2× Arena ROI (default). "
            "Set a larger value for a bigger tracking area, or set equal to ROI radius to match calibration."
        )
        f.addRow("Tracking mask radius (px):", self._arena_tracking_radius_px)
        self._arena_px_per_cm_label = QLabel("—")
        self._arena_px_per_cm_label.setToolTip("Derived from ROI radius and arena diameter")
        f.addRow("px/cm (read-only):", self._arena_px_per_cm_label)
        self._arena_radius_px.valueChanged.connect(self._update_arena_px_per_cm_label)
        self._arena_diameter_value.valueChanged.connect(self._update_arena_px_per_cm_label)
        self._arena_exit_radius_cm = QDoubleSpinBox()
        self._arena_exit_radius_cm.setRange(0.5, 50.0)
        self._arena_exit_radius_cm.setSuffix(" cm")
        f.addRow("Exit radius (cm):", self._arena_exit_radius_cm)
        self._arena_center_x = QDoubleSpinBox()
        self._arena_center_x.setRange(-10000, 10000)
        f.addRow("Arena center X (px):", self._arena_center_x)
        self._arena_center_y = QDoubleSpinBox()
        self._arena_center_y.setRange(-10000, 10000)
        f.addRow("Arena center Y (px):", self._arena_center_y)
        return w

    def _update_arena_px_per_cm_label(self) -> None:
        """Refresh px/cm read-only from diameter and radius in Arena tab."""
        r_px = self._arena_radius_px.value()
        unit = self._arena_diameter_unit.currentData() or "ft"
        val = self._arena_diameter_value.value()
        if unit == "m":
            d_cm = val * M_TO_CM
        else:
            d_cm = val * FT_TO_CM
        if d_cm > 0 and r_px > 0:
            ppc = (2.0 * r_px) / d_cm
            self._arena_px_per_cm_label.setText(f"{ppc:.2f}")
        else:
            self._arena_px_per_cm_label.setText("—")

    def _exit_angles_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self._exit_n_angles = QSpinBox()
        self._exit_n_angles.setRange(1, 16)
        f.addRow("Number of angles:", self._exit_n_angles)
        self._exit_offset_deg = QDoubleSpinBox()
        self._exit_offset_deg.setRange(-360, 360)
        self._exit_offset_deg.setSuffix(" °")
        f.addRow("Offset (deg):", self._exit_offset_deg)
        self._exit_step_deg = QDoubleSpinBox()
        self._exit_step_deg.setRange(0.5, 360)
        self._exit_step_deg.setSuffix(" °")
        f.addRow("Step (deg):", self._exit_step_deg)
        return w

    def _stimulus_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        vast_g = QGroupBox("VAST")
        vast_f = QFormLayout(vast_g)
        self._stimulus_min_at_exit = QCheckBox("Min duty at exit (colder)")
        vast_f.addRow(self._stimulus_min_at_exit)
        self._stimulus_min_duty = QDoubleSpinBox()
        self._stimulus_min_duty.setRange(0, 100)
        self._stimulus_min_duty.setSuffix(" %")
        vast_f.addRow("Min duty %:", self._stimulus_min_duty)
        self._stimulus_max_duty = QDoubleSpinBox()
        self._stimulus_max_duty.setRange(0, 100)
        self._stimulus_max_duty.setSuffix(" %")
        vast_f.addRow("Max duty %:", self._stimulus_max_duty)
        layout.addWidget(vast_g)
        hab_g = QGroupBox("Habituation")
        hab_f = QFormLayout(hab_g)
        self._hab_duty = QDoubleSpinBox()
        self._hab_duty.setRange(0, 100)
        self._hab_duty.setSuffix(" %")
        hab_f.addRow("Habituation training duty %:", self._hab_duty)
        self._wait_not_center_duty = QDoubleSpinBox()
        self._wait_not_center_duty.setRange(0, 100)
        self._wait_not_center_duty.setSuffix(" %")
        self._wait_not_center_duty.setToolTip("Stimulus intensity during Wait exit (VAST and habituation_training only). Default 0.")
        hab_f.addRow("Wait-not-center duty %:", self._wait_not_center_duty)
        layout.addWidget(hab_g)
        return w

    def _session_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self._session_id_edit = QLineEdit()
        self._session_id_edit.setPlaceholderText("e.g. 2025-02-19-A")
        self._session_id_edit.setToolTip("Letters, digits, hyphen, period only (no underscore; used as delimiter in filenames).")
        if HAS_QT:
            self._session_id_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[a-zA-Z0-9.\-]*$")))
        f.addRow("Session ID:", self._session_id_edit)
        self._phase_combo = QComboBox()
        for p in Phase:
            self._phase_combo.addItem(p.value.replace("_", " ").title(), p)
        f.addRow("Phase:", self._phase_combo)
        self._mode_combo = QComboBox()
        for m in TrialMode:
            self._mode_combo.addItem(m.value.replace("_", " ").title(), m)
        f.addRow("Mode:", self._mode_combo)
        self._session_num_animals = QSpinBox()
        self._session_num_animals.setRange(1, 50)
        self._session_num_animals.valueChanged.connect(self._on_num_animals_changed)
        f.addRow("Number of animals:", self._session_num_animals)
        self._session_num_trials = QSpinBox()
        self._session_num_trials.setRange(1, 99)
        f.addRow("Trials per session:", self._session_num_trials)
        self._session_max_trial_s = QDoubleSpinBox()
        self._session_max_trial_s.setRange(1, 3600)
        self._session_max_trial_s.setSuffix(" s")
        f.addRow("Max trial duration (s):", self._session_max_trial_s)
        self._session_iti_s = QDoubleSpinBox()
        self._session_iti_s.setRange(0, 600)
        self._session_iti_s.setSuffix(" s")
        f.addRow("ITI (s):", self._session_iti_s)
        self._session_seed = QLineEdit()
        self._session_seed.setPlaceholderText("None, integer, legacy, or path to legacy .h5")
        f.addRow("Seed:", self._session_seed)
        out_row = QHBoxLayout()
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setPlaceholderText("Output folder for H5 file; videos in <h5_stem>_vids subfolder")
        out_row.addWidget(self._output_dir_edit)
        self._output_browse_btn = QPushButton("Browse…")
        self._output_browse_btn.clicked.connect(self._on_browse_output)
        out_row.addWidget(self._output_browse_btn)
        f.addRow("Output folder:", out_row)
        self._h5_filename_edit = QLineEdit()
        self._h5_filename_edit.setPlaceholderText("trials.h5")
        f.addRow("H5 filename:", self._h5_filename_edit)
        return w

    def _on_num_animals_changed(self) -> None:
        """Resize animals table when number of animals changes so dialog stays in sync."""
        n = max(self._session_num_animals.value(), 1)
        self._animals_table.setRowCount(n)
        for i in range(n):
            if self._animals_table.item(i, 0) is None:
                self._animals_table.setItem(i, 0, QTableWidgetItem(""))
            for col in (1, 2, 3, 4, 5):
                if self._animals_table.item(i, col) is None:
                    self._animals_table.setItem(i, col, QTableWidgetItem(""))

    def _on_browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Output folder")
        if path:
            self._output_dir_edit.setText(path)

    def _on_browse_sleap_model(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "SLEAP model directory")
        if path:
            self._sleap_model_path_edit.setText(path)

    def _animals_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self._animals_table = QTableWidget()
        self._animals_table.setColumnCount(6)
        self._animals_table.setHorizontalHeaderLabels(["Animal ID", "Sex", "Strain", "Treatment", "Drug", "Notes"])
        self._animals_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._animals_table)
        return w

    def _tracking_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Options (show overlay, async, backup only)
        options_g = QGroupBox("Options")
        options_ly = QVBoxLayout(options_g)
        self._track_show_cb = QCheckBox("Show tracking overlay")
        self._track_show_cb.setToolTip("Draw tracking overlay on camera preview.")
        options_ly.addWidget(self._track_show_cb)
        self._track_async_cb = QCheckBox("Async tracking (smoother display)")
        self._track_async_cb.setToolTip("Run tracking in background thread; display uses last result.")
        options_ly.addWidget(self._track_async_cb)
        self._track_backup_only_cb = QCheckBox("Backup tracking only (ignore SLEAP model)")
        self._track_backup_only_cb.setToolTip("Use only the adaptive-threshold backup tracker.")
        options_ly.addWidget(self._track_backup_only_cb)
        layout.addWidget(options_g)

        # Fallback section
        fallback_g = QGroupBox("Fallback")
        f = QFormLayout(fallback_g)
        self._fallback_min_area = QSpinBox()
        self._fallback_min_area.setRange(1, 10000)
        self._fallback_min_area.setToolTip("Minimum contour area (px) to count as a blob. Smaller = more sensitive.")
        f.addRow("Min area (px):", self._fallback_min_area)
        self._fallback_max_area = QSpinBox()
        self._fallback_max_area.setRange(0, 1000000)
        self._fallback_max_area.setSpecialValueText("None")
        self._fallback_max_area.setToolTip("Maximum contour area (px). 0 = no limit. Use to reject huge blobs (e.g. whole arena).")
        f.addRow("Max area (px, 0=off):", self._fallback_max_area)
        self._fallback_morph_kernel = QSpinBox()
        self._fallback_morph_kernel.setRange(1, 31)
        self._fallback_morph_kernel.setSingleStep(2)
        self._fallback_morph_kernel.setToolTip("Morphology kernel size (odd). Close holes, remove noise.")
        f.addRow("Morph kernel size:", self._fallback_morph_kernel)
        self._fallback_range_low = QSpinBox()
        self._fallback_range_low.setRange(0, 255)
        self._fallback_range_low.setToolTip("Intensity range: minimum (0–255). Pixel on if intensity in [low, high].")
        f.addRow("Range low (0–255):", self._fallback_range_low)
        self._fallback_range_high = QSpinBox()
        self._fallback_range_high.setRange(0, 255)
        self._fallback_range_high.setValue(255)
        self._fallback_range_high.setToolTip("Intensity range: maximum (0–255). Pixel on if intensity in [low, high].")
        f.addRow("Range high (0–255):", self._fallback_range_high)
        self._fallback_max_jump = QDoubleSpinBox()
        self._fallback_max_jump.setRange(0, 2000)
        self._fallback_max_jump.setDecimals(0)
        self._fallback_max_jump.setSpecialValueText("None")
        self._fallback_max_jump.setToolTip("Max allowed jump (px) from last position. 0 = no limit. Larger values reduce jitter rejection.")
        f.addRow("Max jump (px, 0=off):", self._fallback_max_jump)
        self._fallback_selection_mode = QComboBox()
        self._fallback_selection_mode.addItem("Largest by area", "largest")
        self._fallback_selection_mode.addItem("Closest to last position", "closest")
        self._fallback_selection_mode.addItem("Closest, else largest (if jump too far)", "closest_else_largest")
        self._fallback_selection_mode.setToolTip("How to choose which blob to track when several are detected.")
        f.addRow("Blob selection:", self._fallback_selection_mode)
        self._fallback_min_circularity = QDoubleSpinBox()
        self._fallback_min_circularity.setRange(0, 1.0)
        self._fallback_min_circularity.setDecimals(2)
        self._fallback_min_circularity.setSingleStep(0.05)
        self._fallback_min_circularity.setSpecialValueText("Off")
        self._fallback_min_circularity.setToolTip("Reject blobs with circularity below this (4π×area/perimeter²). 0 = off. Use to filter elongated shapes (e.g. tail, cable).")
        f.addRow("Min circularity (0=off):", self._fallback_min_circularity)
        self._fallback_show_blob_cb = QCheckBox("Show blob overlay")
        self._fallback_show_blob_cb.setChecked(True)
        self._fallback_show_blob_cb.setToolTip("Draw green tint where fallback tracker detected the blob. Disable for better FPS when tracking in-range pixels.")
        f.addRow("", self._fallback_show_blob_cb)
        self._fallback_max_contours = QSpinBox()
        self._fallback_max_contours.setRange(0, 10000)
        self._fallback_max_contours.setSpecialValueText("No limit")
        self._fallback_max_contours.setToolTip("Max contours to consider per frame (0 = no limit). Keeps largest by area. Can reduce FPS drops when many in-range pixels.")
        f.addRow("Max contours (0=off):", self._fallback_max_contours)
        layout.addWidget(fallback_g)

        # SLEAP section
        sleap_g = QGroupBox("SLEAP")
        sleap_f = QFormLayout(sleap_g)
        sleap_path_row = QHBoxLayout()
        self._sleap_model_path_edit = QLineEdit()
        self._sleap_model_path_edit.setPlaceholderText("Optional: path to single-instance model dir")
        self._sleap_model_path_edit.setToolTip("Folder with training_config.yaml and best.ckpt (single-instance). Leave empty for backup tracker only.")
        sleap_path_row.addWidget(self._sleap_model_path_edit)
        self._sleap_browse_btn = QPushButton("Browse…")
        self._sleap_browse_btn.clicked.connect(self._on_browse_sleap_model)
        sleap_path_row.addWidget(self._sleap_browse_btn)
        sleap_f.addRow("SLEAP model (dir):", sleap_path_row)
        self._fallback_min_sleap_nodes = QSpinBox()
        self._fallback_min_sleap_nodes.setRange(1, 64)
        self._fallback_min_sleap_nodes.setValue(1)
        self._fallback_min_sleap_nodes.setToolTip("SLEAP: use backup tracker if fewer than this many nodes pass the confidence threshold. 1 = use SLEAP whenever at least one node passes.")
        sleap_f.addRow("Min SLEAP nodes (else backup):", self._fallback_min_sleap_nodes)
        self._sleap_confidence_pct = QSpinBox()
        self._sleap_confidence_pct.setRange(0, 100)
        self._sleap_confidence_pct.setSuffix(" %")
        self._sleap_confidence_pct.setToolTip(
            "Per-node minimum confidence: nodes above this are kept; nodes below are rejected. If no nodes pass, backup tracker is used."
        )
        sleap_f.addRow("Confidence (%):", self._sleap_confidence_pct)
        self._sleap_every_n = QSpinBox()
        self._sleap_every_n.setRange(1, 5)
        self._sleap_every_n.setToolTip("1 = every frame; 2+ = run SLEAP every N-th frame (reuse result for others, better FPS).")
        sleap_f.addRow("Run SLEAP every (frames):", self._sleap_every_n)
        self._fallback_node_max_jump = QDoubleSpinBox()
        self._fallback_node_max_jump.setRange(0, 500)
        self._fallback_node_max_jump.setDecimals(0)
        self._fallback_node_max_jump.setSpecialValueText("Off")
        self._fallback_node_max_jump.setToolTip("SLEAP nodes: invalidate a node if it moves more than this (px) from previous frame. 0 = off.")
        sleap_f.addRow("Node max jump (px, 0=off):", self._fallback_node_max_jump)
        self._sleap_exit_min_keypoints = QSpinBox()
        self._sleap_exit_min_keypoints.setRange(1, 64)
        self._sleap_exit_min_keypoints.setValue(2)
        self._sleap_exit_min_keypoints.setToolTip("VAST success with SLEAP source: require at least this many valid keypoints inside the exit zone.")
        sleap_f.addRow("Exit success min keypoints:", self._sleap_exit_min_keypoints)
        self._fallback_exit_blob_overlap_pct = QDoubleSpinBox()
        self._fallback_exit_blob_overlap_pct.setRange(0.0, 100.0)
        self._fallback_exit_blob_overlap_pct.setDecimals(1)
        self._fallback_exit_blob_overlap_pct.setSuffix(" %")
        self._fallback_exit_blob_overlap_pct.setValue(15.0)
        self._fallback_exit_blob_overlap_pct.setToolTip("VAST success with fallback source: minimum percent of blob pixels overlapping the exit zone.")
        sleap_f.addRow("Fallback blob overlap for success:", self._fallback_exit_blob_overlap_pct)
        layout.addWidget(sleap_g)

        layout.addStretch()
        return w

    def _push_session_id_to_parent(self) -> None:
        """Sync Session ID from dialog to parent main window and trial controller."""
        parent = self.parent()
        if parent is None:
            return
        if hasattr(parent, "_session_id_edit"):
            parent._session_id_edit.setText(self._session_id_edit.text().strip())
        if hasattr(parent, "_trial_controller"):
            parent._trial_controller.apply_session_controls(self._session_id_edit.text().strip())

    def _on_apply(self) -> None:
        """Write config and notify parent; keep dialog open."""
        self._write_to_config()
        parent = self.parent()
        self._push_session_id_to_parent()
        if parent is not None and hasattr(parent, "_apply_config_to_ui"):
            parent._apply_config_to_ui()
        if HAS_QT and parent is not None and hasattr(parent, "statusBar") and parent.statusBar is not None:
            parent.statusBar().showMessage("Settings applied.")

    def _fill_from_config(self) -> None:
        c = self._config
        a = c.arena
        unit = a.diameter_display_unit or "ft"
        if unit == "m":
            self._arena_diameter_value.setValue(a.diameter_m)
        else:
            self._arena_diameter_value.setValue(a.diameter_ft)
        idx = self._arena_diameter_unit.findData(unit)
        if idx >= 0:
            self._arena_diameter_unit.setCurrentIndex(idx)
        self._arena_radius_px.setValue(int(a.radius_px))
        self._arena_tracking_radius_px.setValue(int(a.tracking_radius_px))
        self._arena_center_pct.setValue(a.center_pct)
        self._arena_exit_radius_cm.setValue(a.exit_radius_cm)
        self._arena_center_x.setValue(a.arena_center_x_px)
        self._arena_center_y.setValue(a.arena_center_y_px)
        self._update_arena_px_per_cm_label()
        e = c.exit_angles
        self._exit_n_angles.setValue(e.n_angles)
        self._exit_offset_deg.setValue(e.offset_deg)
        self._exit_step_deg.setValue(e.step_deg)
        s = c.stimulus
        self._stimulus_min_at_exit.setChecked(s.min_at_exit)
        self._stimulus_min_duty.setValue(s.min_duty_pct)
        self._stimulus_max_duty.setValue(s.max_duty_pct)
        sess = c.session
        self._session_num_animals.setValue(sess.num_animals)
        self._session_num_trials.setValue(sess.num_trials)
        self._session_max_trial_s.setValue(sess.max_trial_duration_s)
        self._session_iti_s.setValue(sess.iti_s)
        if sess.seed == -1 and sess.legacy_seed_db_path:
            self._session_seed.setText(sess.legacy_seed_db_path)
        elif sess.seed == -1:
            self._session_seed.setText("legacy")
        else:
            self._session_seed.setText(str(sess.seed) if sess.seed is not None else "")
        self._output_dir_edit.setText(c.output_dir or "")
        self._h5_filename_edit.setText(c.h5_filename or "trials.h5")
        parent = self.parent()
        if parent is not None and hasattr(parent, "_session_id_edit"):
            self._session_id_edit.setText((parent._session_id_edit.text() or "").strip())
        self._hab_duty.setValue(c.hab_training_duty_pct)
        self._wait_not_center_duty.setValue(c.wait_not_center_duty_pct)
        run_phase = c.run_phase or "habituation"
        try:
            phase_enum = Phase(run_phase)
        except ValueError:
            phase_enum = Phase.HABITUATION
        idx = self._phase_combo.findData(phase_enum)
        if idx >= 0:
            self._phase_combo.setCurrentIndex(idx)
        else:
            self._phase_combo.setCurrentIndex(0)
        run_mode = c.run_mode or "continuous"
        try:
            mode_enum = TrialMode(run_mode.lower())
        except ValueError:
            mode_enum = TrialMode.CONTINUOUS
        idx = self._mode_combo.findData(mode_enum)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        else:
            self._mode_combo.setCurrentIndex(0)
        # Animals table
        self._animals_table.setRowCount(max(len(sess.animals), 1))
        for i, animal in enumerate(sess.animals):
            self._animals_table.setItem(i, 0, QTableWidgetItem(animal.animal_id or ""))
            self._animals_table.setItem(i, 1, QTableWidgetItem(animal.sex or ""))
            self._animals_table.setItem(i, 2, QTableWidgetItem(animal.strain or ""))
            self._animals_table.setItem(i, 3, QTableWidgetItem(animal.tx or ""))
            self._animals_table.setItem(i, 4, QTableWidgetItem(animal.drug or ""))
            self._animals_table.setItem(i, 5, QTableWidgetItem(animal.notes or ""))
        if not sess.animals:
            self._animals_table.setItem(0, 0, QTableWidgetItem(""))
        # Fallback tracking
        ft = c.fallback_tracking or FallbackTrackingConfig()
        self._fallback_min_area.setValue(ft.min_area)
        self._fallback_max_area.setValue(ft.max_area)
        self._fallback_morph_kernel.setValue(ft.morph_kernel_size | 1)
        self._fallback_max_jump.setValue(ft.max_jump_px)
        idx_sm = self._fallback_selection_mode.findData(getattr(ft, "selection_mode", "closest_else_largest"))
        if idx_sm >= 0:
            self._fallback_selection_mode.setCurrentIndex(idx_sm)
        else:
            self._fallback_selection_mode.setCurrentIndex(2)  # closest_else_largest
        self._fallback_min_circularity.setValue(getattr(ft, "min_circularity", 0.0))
        self._fallback_range_low.setValue(getattr(ft, "range_low", 0))
        self._fallback_range_high.setValue(getattr(ft, "range_high", 255))
        self._fallback_node_max_jump.setValue(getattr(ft, "node_max_jump_px", 0.0))
        self._fallback_min_sleap_nodes.setValue(getattr(ft, "min_sleap_nodes", 1))
        self._fallback_show_blob_cb.setChecked(getattr(ft, "show_blob_overlay", True))
        self._fallback_max_contours.setValue(getattr(ft, "max_contours", 0))
        # Tracking options and SLEAP path
        self._track_show_cb.setChecked(getattr(c, "track_show", True))
        self._track_async_cb.setChecked(getattr(c, "track_async", False))
        self._track_backup_only_cb.setChecked(getattr(c, "track_backup_only", False))
        self._sleap_model_path_edit.setText(getattr(c, "sleap_model_path", "") or "")
        # SLEAP
        self._sleap_confidence_pct.setValue(getattr(c, "sleap_confidence_pct", 50))
        self._sleap_every_n.setValue(max(1, min(5, getattr(c, "sleap_every_n", 1))))
        self._sleap_exit_min_keypoints.setValue(max(1, int(getattr(c, "sleap_exit_min_keypoints", 2))))
        self._fallback_exit_blob_overlap_pct.setValue(max(0.0, min(100.0, float(getattr(c, "fallback_exit_blob_overlap_pct", 15.0)))))

    def _write_to_config(self) -> None:
        c = self._config
        unit = self._arena_diameter_unit.currentData() or "ft"
        val = self._arena_diameter_value.value()
        if unit == "m":
            c.arena.diameter_cm = val * M_TO_CM
        else:
            c.arena.diameter_cm = val * FT_TO_CM
        c.arena.diameter_display_unit = unit
        c.arena.radius_px = float(self._arena_radius_px.value())
        c.arena.tracking_radius_px = float(self._arena_tracking_radius_px.value())
        c.arena.center_pct = self._arena_center_pct.value()
        c.arena.exit_radius_cm = self._arena_exit_radius_cm.value()
        c.arena.arena_center_x_px = self._arena_center_x.value()
        c.arena.arena_center_y_px = self._arena_center_y.value()
        c.exit_angles.n_angles = self._exit_n_angles.value()
        c.exit_angles.offset_deg = self._exit_offset_deg.value()
        c.exit_angles.step_deg = self._exit_step_deg.value()
        c.stimulus.min_at_exit = self._stimulus_min_at_exit.isChecked()
        c.stimulus.min_duty_pct = self._stimulus_min_duty.value()
        c.stimulus.max_duty_pct = self._stimulus_max_duty.value()
        c.session.num_animals = self._session_num_animals.value()
        c.session.num_trials = self._session_num_trials.value()
        c.session.max_trial_duration_s = self._session_max_trial_s.value()
        c.session.iti_s = self._session_iti_s.value()
        c.session.seed, c.session.legacy_seed_db_path = _parse_seed(self._session_seed.text())
        c.output_dir = self._output_dir_edit.text().strip() or None
        c.h5_filename = self._h5_filename_edit.text().strip() or "trials.h5"
        c.hab_training_duty_pct = self._hab_duty.value()
        c.wait_not_center_duty_pct = self._wait_not_center_duty.value()
        p = self._phase_combo.currentData()
        if p is not None:
            c.run_phase = p.value
        m = self._mode_combo.currentData()
        if m is not None:
            c.run_mode = m.value
        # Animals
        rows = self._animals_table.rowCount()
        c.session.animals = []
        for i in range(rows):
            id_item = self._animals_table.item(i, 0)
            sex_item = self._animals_table.item(i, 1)
            strain_item = self._animals_table.item(i, 2)
            tx_item = self._animals_table.item(i, 3)
            drug_item = self._animals_table.item(i, 4)
            notes_item = self._animals_table.item(i, 5)
            aid = (id_item.text() or "").strip() if id_item else ""
            if not aid and i >= c.session.num_animals:
                continue
            c.session.animals.append(AnimalInfo(
                animal_id=aid or str(1000 + i),
                tx=(tx_item.text() or "").strip() or None if tx_item else None,
                strain=(strain_item.text() or "").strip() or None if strain_item else None,
                sex=(sex_item.text() or "").strip() or None if sex_item else None,
                drug=(drug_item.text() or "").strip() or None if drug_item else None,
                notes=(notes_item.text() or "").strip() or None if notes_item else None,
            ))
        c.session.ensure_animals()
        # Fallback tracking
        ft = getattr(c, "fallback_tracking", None)
        if ft is None:
            c.fallback_tracking = FallbackTrackingConfig()
            ft = c.fallback_tracking
        ft.min_area = self._fallback_min_area.value()
        ft.max_area = self._fallback_max_area.value()
        ft.morph_kernel_size = self._fallback_morph_kernel.value() | 1
        ft.max_jump_px = self._fallback_max_jump.value()
        sm = self._fallback_selection_mode.currentData()
        if sm is not None:
            ft.selection_mode = str(sm)
        ft.min_circularity = self._fallback_min_circularity.value()
        ft.range_low = self._fallback_range_low.value()
        ft.range_high = self._fallback_range_high.value()
        ft.node_max_jump_px = self._fallback_node_max_jump.value()
        ft.min_sleap_nodes = self._fallback_min_sleap_nodes.value()
        ft.show_blob_overlay = self._fallback_show_blob_cb.isChecked()
        ft.max_contours = max(0, self._fallback_max_contours.value())
        # Tracking options and SLEAP path
        c.track_show = self._track_show_cb.isChecked()
        c.track_async = self._track_async_cb.isChecked()
        c.track_backup_only = self._track_backup_only_cb.isChecked()
        c.sleap_model_path = (self._sleap_model_path_edit.text() or "").strip()
        # SLEAP
        c.sleap_confidence_pct = max(0, min(100, self._sleap_confidence_pct.value()))
        c.sleap_every_n = max(1, min(5, self._sleap_every_n.value()))
        c.sleap_exit_min_keypoints = max(1, self._sleap_exit_min_keypoints.value())
        c.fallback_exit_blob_overlap_pct = max(0.0, min(100.0, self._fallback_exit_blob_overlap_pct.value()))

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_last_tab()
        super().closeEvent(event)

    def accept(self) -> None:
        self._save_last_tab()
        self._write_to_config()
        self._push_session_id_to_parent()
        parent = self.parent()
        if parent is not None and hasattr(parent, "_apply_config_to_ui"):
            parent._apply_config_to_ui()
        super().accept()

    def reject(self) -> None:
        self._save_last_tab()
        super().reject()
