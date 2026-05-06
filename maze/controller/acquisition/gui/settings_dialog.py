"""Settings dialog with task, session, tracking, animals, and trial schedule tabs."""

from __future__ import annotations

from typing import Optional

from ....core.session_slots import slot_to_animal_trial
from ..shared_config import (
    AcquisitionConfig,
    AnimalInfo,
    FallbackTrackingConfig,
    ensure_exit_schedule_indices_length,
)
from ..vast.config import FT_TO_CM, M_TO_CM, VastControllerConfig
from ..radial_arm.config import RadialArmControllerConfig, sync_ram_px_per_cm
from ..task_registry import AcquisitionMode, get_task_spec
from ..vast.arena import latin_square_exit_index

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

_SETTINGS_ORG = "Maze"
_SETTINGS_APP = "Acquisition"
_KEY_LAST_SETTINGS_TAB = "last_settings_tab"


def _parse_seed_auto_value(text: str) -> Optional[int]:
    s = (text or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


class SettingsDialog(QDialog):
    """Settings window: modeless so you can use main window while it's open. Apply writes config and keeps dialog open."""

    def __init__(
        self,
        config: AcquisitionConfig,
        parent: Optional[QWidget] = None,
        *,
        task_mode: AcquisitionMode = "vast",
        initial_tab_index: Optional[int] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._task_mode = task_mode
        self._task_spec = get_task_spec(task_mode)
        self.setWindowTitle("Settings")
        self.setWindowModality(Qt.WindowModality.NonModal)
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._tracking_tab(), "Tracking")
        self._tabs.addTab(self._task_tab(), self._task_spec.task_tab_label)
        self._tabs.addTab(self._session_tab(), "Session")
        self._tabs.addTab(self._animals_tab(), "Animals")
        self._tabs.addTab(self._trial_schedule_tab(), "Trial schedule")
        layout.addWidget(self._tabs)
        if initial_tab_index is not None and 0 <= initial_tab_index < self._tabs.count():
            self._tabs.setCurrentIndex(initial_tab_index)
        else:
            s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
            last = s.value(_KEY_LAST_SETTINGS_TAB, 0, type=int)
            if 0 <= last < self._tabs.count():
                self._tabs.setCurrentIndex(last)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        if self._task_mode == "ram":
            for _w in (
                self._ram_center_midedge_cm,
                self._ram_apothem_px,
                self._ram_template_rotation_deg,
                self._ram_template_center_x,
                self._ram_template_center_y,
            ):
                _w.valueChanged.connect(self._update_ram_px_per_cm_label)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        apply_btn = bbox.button(QDialogButtonBox.StandardButton.Apply)
        self._apply_btn = apply_btn
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

    def set_config(self, config: AcquisitionConfig) -> None:
        """Replace the backing config object and immediately refresh all fields."""
        self._config = config
        self._fill_from_config()

    def refresh_from_config(self) -> None:
        """Refresh widgets from the current backing config object."""
        self._fill_from_config()

    def set_apply_enabled(self, enabled: bool) -> None:
        """Enable Apply; disabled e.g. while TRIAL_RUNNING so settings are not applied mid-maze."""
        self._apply_btn.setEnabled(enabled)
        if enabled:
            self._apply_btn.setToolTip("Apply changes without closing this window.")
        else:
            self._apply_btn.setToolTip("Apply is disabled while a trial is running.")

    def _update_ram_px_per_cm_label(self, *_args) -> None:
        """Refresh read-only px/cm from hub apothem (px) and center mid-edge span (cm)."""
        if self._task_mode != "ram":
            return
        mid_cm = self._ram_center_midedge_cm.value()
        ap_cm = mid_cm / 2.0
        ap_px = self._ram_apothem_px.value()
        if ap_cm > 0.0 and ap_px > 0.0:
            self._ram_px_per_cm_label.setText(f"{ap_px / ap_cm:.4f}")
        else:
            self._ram_px_per_cm_label.setText("—")

    def _on_tab_changed(self, index: int) -> None:
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue(_KEY_LAST_SETTINGS_TAB, index)

    def _save_last_tab(self) -> None:
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue(_KEY_LAST_SETTINGS_TAB, self._tabs.currentIndex())

    def _task_tab(self) -> QWidget:
        if self._task_mode == "ram":
            return self._ram_task_tab()
        return self._vast_task_tab()

    def _vast_task_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(self._wrap_task_group("Arena", self._arena_tab()))
        layout.addWidget(self._wrap_task_group("Exit angles", self._exit_angles_tab()))
        layout.addWidget(self._wrap_task_group("Stimulus", self._stimulus_tab()))
        layout.addStretch()
        return w

    def _wrap_task_group(self, title: str, widget: QWidget) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.addWidget(widget)
        return box

    def _ram_task_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        template_g = QGroupBox("Template geometry")
        template_f = QFormLayout(template_g)
        self._ram_center_midedge_cm = QDoubleSpinBox()
        self._ram_center_midedge_cm.setRange(1.0, 500.0)
        self._ram_center_midedge_cm.setSuffix(" cm")
        template_f.addRow("Center mid-edge span:", self._ram_center_midedge_cm)
        self._ram_arm_length_cm = QDoubleSpinBox()
        self._ram_arm_length_cm.setRange(1.0, 500.0)
        self._ram_arm_length_cm.setSuffix(" cm")
        template_f.addRow("Arm length:", self._ram_arm_length_cm)
        self._ram_arm_width_cm = QDoubleSpinBox()
        self._ram_arm_width_cm.setRange(1.0, 200.0)
        self._ram_arm_width_cm.setSuffix(" cm")
        template_f.addRow("Arm width:", self._ram_arm_width_cm)
        self._ram_arm_split_cm = QDoubleSpinBox()
        self._ram_arm_split_cm.setRange(0.0, 500.0)
        self._ram_arm_split_cm.setSuffix(" cm")
        template_f.addRow("Arm split:", self._ram_arm_split_cm)
        self._ram_hole_radius_cm = QDoubleSpinBox()
        self._ram_hole_radius_cm.setRange(0.1, 50.0)
        self._ram_hole_radius_cm.setSuffix(" cm")
        template_f.addRow("Hole radius:", self._ram_hole_radius_cm)
        self._ram_hole_inset_cm = QDoubleSpinBox()
        self._ram_hole_inset_cm.setRange(0.0, 100.0)
        self._ram_hole_inset_cm.setSuffix(" cm")
        template_f.addRow("Hole inset from arm end:", self._ram_hole_inset_cm)
        layout.addWidget(template_g)

        calibration_g = QGroupBox("Placement and editing")
        calibration_f = QFormLayout(calibration_g)
        self._ram_template_center_x = QDoubleSpinBox()
        self._ram_template_center_x.setRange(-10000.0, 10000.0)
        calibration_f.addRow("Template center X (px):", self._ram_template_center_x)
        self._ram_template_center_y = QDoubleSpinBox()
        self._ram_template_center_y.setRange(-10000.0, 10000.0)
        calibration_f.addRow("Template center Y (px):", self._ram_template_center_y)
        self._ram_template_rotation_deg = QDoubleSpinBox()
        self._ram_template_rotation_deg.setRange(-360.0, 360.0)
        self._ram_template_rotation_deg.setSuffix(" deg")
        calibration_f.addRow("Template rotation:", self._ram_template_rotation_deg)
        self._ram_apothem_px = QDoubleSpinBox()
        self._ram_apothem_px.setRange(0.0, 8000.0)
        self._ram_apothem_px.setDecimals(2)
        self._ram_apothem_px.setToolTip(
            "Hub apothem in pixels (center to flat side). With center mid-edge span (cm), "
            "defines read-only px/cm like VAST arena ROI radius + diameter."
        )
        calibration_f.addRow("Hub apothem (px):", self._ram_apothem_px)
        self._ram_px_per_cm_label = QLabel("—")
        self._ram_px_per_cm_label.setToolTip("Derived: apothem_px / (center mid-edge span / 2)")
        calibration_f.addRow("px/cm (read-only):", self._ram_px_per_cm_label)
        self._ram_tracking_mask_margin_px = QSpinBox()
        self._ram_tracking_mask_margin_px.setRange(0, 9999)
        self._ram_tracking_mask_margin_px.setToolTip(
            "Extra pixels around template bbox for tracking crop. 0 = auto (~20% of bbox half-extent), "
            "similar to VAST when tracking mask radius uses the 1.2× default."
        )
        calibration_f.addRow("Tracking mask margin (px, 0=auto):", self._ram_tracking_mask_margin_px)
        # TODO(RAM edit tools): wire this into per-region editing/highlighting; currently metadata-only.
        self._ram_edit_region_name = QLineEdit()
        self._ram_edit_region_name.setPlaceholderText("e.g. arm0_front")
        calibration_f.addRow("Active edit region:", self._ram_edit_region_name)
        self._ram_preview_set_center_from_click_cb = QCheckBox(
            "Place RAM template from next click on preview"
        )
        self._ram_preview_set_center_from_click_cb.setToolTip(
            "When checked, the next left-click on the live preview sets template center X/Y."
        )
        self._ram_preview_set_center_from_click_cb.stateChanged.connect(
            self._on_ram_preview_set_center_clicked_changed
        )
        calibration_f.addRow(self._ram_preview_set_center_from_click_cb)
        layout.addWidget(calibration_g)

        trial_g = QGroupBox("Task and stimulus")
        trial_f = QFormLayout(trial_g)
        self._ram_stimulus_enabled = QCheckBox("Enable speaker stimulus")
        trial_f.addRow(self._ram_stimulus_enabled)
        self._ram_speaker_device_name = QLineEdit()
        trial_f.addRow("Speaker device:", self._ram_speaker_device_name)
        self._ram_speaker_volume_pct = QDoubleSpinBox()
        self._ram_speaker_volume_pct.setRange(0.0, 100.0)
        self._ram_speaker_volume_pct.setSuffix(" %")
        trial_f.addRow("Speaker volume:", self._ram_speaker_volume_pct)
        self._ram_stimulus_frequency_hz = QDoubleSpinBox()
        self._ram_stimulus_frequency_hz.setRange(0.0, 50000.0)
        self._ram_stimulus_frequency_hz.setSuffix(" Hz")
        trial_f.addRow("Stimulus frequency:", self._ram_stimulus_frequency_hz)
        layout.addWidget(trial_g)
        layout.addStretch()
        return w

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
        self._preview_set_center_from_click_cb = QCheckBox(
            "Set arena center from next click on preview"
        )
        self._preview_set_center_from_click_cb.setToolTip(
            "When checked, the next left-click on the live preview sets arena center X/Y."
        )
        self._preview_set_center_from_click_cb.stateChanged.connect(
            self._on_vast_preview_set_center_clicked_changed
        )
        f.addRow(self._preview_set_center_from_click_cb)
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
        self._exit_n_angles.valueChanged.connect(self._on_exit_n_angles_changed)
        return w

    def _on_exit_n_angles_changed(self, value: int) -> None:
        if hasattr(self, "_schedule_default_exit_idx"):
            self._schedule_default_exit_idx.setMaximum(max(1, int(value)))

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
        self._session_id_edit.textChanged.connect(self._refresh_trial_schedule_tab)
        f.addRow("Session ID:", self._session_id_edit)
        self._phase_combo = QComboBox()
        for label, value in self._task_spec.phase_options:
            self._phase_combo.addItem(label, value)
        if self._task_spec.phase_options and self._task_spec.phase_label is not None:
            f.addRow(self._task_spec.phase_label, self._phase_combo)
        self._mode_combo = QComboBox()
        for label, value in self._task_spec.mode_options:
            self._mode_combo.addItem(label, value)
        self._mode_combo.currentIndexChanged.connect(self._refresh_trial_schedule_tab)
        f.addRow("Mode:", self._mode_combo)
        self._session_num_animals = QSpinBox()
        self._session_num_animals.setRange(1, 50)
        self._session_num_animals.valueChanged.connect(self._on_num_animals_changed)
        self._session_num_animals.valueChanged.connect(self._on_session_slots_changed)
        f.addRow("Number of animals:", self._session_num_animals)
        self._session_num_trials = QSpinBox()
        self._session_num_trials.setRange(1, 99)
        self._session_num_trials.valueChanged.connect(self._on_session_slots_changed)
        f.addRow("Trials per session:", self._session_num_trials)
        self._session_max_trial_s = QDoubleSpinBox()
        self._session_max_trial_s.setRange(1, 3600)
        self._session_max_trial_s.setSuffix(" s")
        f.addRow("Max trial duration (s):", self._session_max_trial_s)
        self._session_iti_s = QDoubleSpinBox()
        self._session_iti_s.setRange(0, 600)
        self._session_iti_s.setSuffix(" s")
        f.addRow("ITI (s):", self._session_iti_s)
        self._virtual_duration_override_s = QDoubleSpinBox()
        self._virtual_duration_override_s.setRange(0.0, 24 * 3600.0)
        self._virtual_duration_override_s.setDecimals(3)
        self._virtual_duration_override_s.setSuffix(" s")
        self._virtual_duration_override_s.setToolTip(
            "Per-profile override for virtual source duration. 0 = use container FPS. "
            "When >0, effective playback FPS = frame_count / override duration."
        )
        f.addRow("Virtual duration override (s):", self._virtual_duration_override_s)
        self._session_seed_mode = QComboBox()
        self._session_seed_mode.addItem("Auto", "auto")
        self._session_seed_mode.addItem("Legacy", "legacy")
        self._session_seed_mode.addItem("Manual", "manual")
        self._session_seed_mode.currentIndexChanged.connect(
            self._sync_seed_value_widget_state
        )
        f.addRow("Seed mode:", self._session_seed_mode)
        self._session_seed_value = QLineEdit()
        self._session_seed_value.setPlaceholderText("Auto: integer seed | Legacy: path to legacy .h5")
        f.addRow("Seed value:", self._session_seed_value)
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

    def _trial_schedule_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        form = QFormLayout()
        self._schedule_default_exit_idx = QSpinBox()
        self._schedule_default_exit_idx.setRange(1, 16)
        self._schedule_default_exit_idx.setToolTip(
            "Default exit index (1-based) used when creating or resizing manual schedules."
        )
        form.addRow("Default exit index (1-based):", self._schedule_default_exit_idx)
        self._schedule_seed_mode_hint = QLabel("")
        self._schedule_seed_mode_hint.setWordWrap(True)
        form.addRow("", self._schedule_seed_mode_hint)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self._schedule_apply_default_btn = QPushButton("Apply default to all slots")
        self._schedule_apply_default_btn.clicked.connect(self._on_schedule_apply_default_to_all)
        actions.addWidget(self._schedule_apply_default_btn)
        actions.addStretch()
        layout.addLayout(actions)

        self._schedule_table = QTableWidget(0, 5)
        self._schedule_table.setHorizontalHeaderLabels(
            ["Index", "Animal ID", "Trial", "Exit", "Source"]
        )
        self._schedule_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._schedule_table)
        return w

    def _refresh_trial_schedule_tab(self) -> None:
        c = self._config
        n_a = max(0, int(c.session.num_animals))
        n_t = max(0, int(c.session.num_trials))
        total = max(0, n_a * n_t)
        seed_mode = str(c.session.seed_mode or "auto")
        manual = seed_mode == "manual"
        n_exits = max(1, int(self._task_spec.get_num_exits(c)))
        default_idx = max(0, min(n_exits - 1, int(self._task_spec.get_default_exit_index(c))))
        self._schedule_default_exit_idx.setMaximum(n_exits)
        self._schedule_default_exit_idx.setValue(default_idx + 1)
        ensure_exit_schedule_indices_length(
            c.session,
            n_exits=n_exits,
            default_exit_index=default_idx,
        )

        if manual:
            self._schedule_seed_mode_hint.setText(
                "Manual seed mode: table values are editable and used per slot."
            )
        else:
            self._schedule_seed_mode_hint.setText(
                "Non-manual seed mode: table is read-only preview."
            )

        mode = self._task_spec.get_mode_value(c)
        sid = (self._session_id_edit.text() or "").strip() or "S"
        c.session.ensure_animals()
        animals = c.session.animals
        raw = c.session.exit_schedule_indices or []

        self._schedule_apply_default_btn.setEnabled(bool(manual))
        self._schedule_table.blockSignals(True)
        self._schedule_table.setRowCount(total)
        for slot in range(total):
            aidx, tidx = slot_to_animal_trial(slot, n_a, n_t, mode)
            aid = (
                str(animals[aidx % max(1, len(animals))].animal_id)
                if animals
                else str(1000 + aidx)
            )
            self._schedule_table.setItem(slot, 0, QTableWidgetItem(str(slot)))
            self._schedule_table.setItem(slot, 1, QTableWidgetItem(aid))
            self._schedule_table.setItem(slot, 2, QTableWidgetItem(f"T{tidx + 1:02d}"))
            if manual and slot < len(raw):
                exit_idx = max(0, min(n_exits - 1, int(raw[slot])))
            else:
                seed_v = c.session.seed_auto_value
                exit_idx = latin_square_exit_index(sid, tidx, n_exits, seed_v)
            it = QTableWidgetItem(str(exit_idx + 1))
            if manual:
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
            else:
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._schedule_table.setItem(slot, 3, it)
            if manual:
                source = "manual schedule"
            elif seed_mode == "legacy":
                source = "legacy-driven (preview only)"
            else:
                source = "auto seed (preview only)"
            src_it = QTableWidgetItem(source)
            src_it.setFlags(src_it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._schedule_table.setItem(slot, 4, src_it)
        self._schedule_table.blockSignals(False)

    def _on_schedule_apply_default_to_all(self) -> None:
        c = self._config
        if str(c.session.seed_mode or "auto") != "manual":
            return
        n_exits = max(1, int(self._task_spec.get_num_exits(c)))
        d = max(1, min(n_exits, int(self._schedule_default_exit_idx.value())))
        self._schedule_table.blockSignals(True)
        for row in range(self._schedule_table.rowCount()):
            item = self._schedule_table.item(row, 3)
            if item is None:
                item = QTableWidgetItem(str(d))
                self._schedule_table.setItem(row, 3, item)
            else:
                item.setText(str(d))
        self._schedule_table.blockSignals(False)

    def _on_num_animals_changed(self) -> None:
        """Resize animals table when number of animals changes so dialog stays in sync."""
        n = max(self._session_num_animals.value(), 1)
        self._animals_table.setRowCount(n)
        for i in range(n):
            if self._animals_table.item(i, 0) is None:
                self._animals_table.setItem(i, 0, QTableWidgetItem(""))
            for col in (1, 2, 3, 4, 5, 6, 7):
                if self._animals_table.item(i, col) is None:
                    self._animals_table.setItem(i, col, QTableWidgetItem(""))

    def _on_session_slots_changed(self, *_args) -> None:
        self._refresh_trial_schedule_tab()

    def _sync_seed_value_widget_state(self) -> None:
        mode = str(self._session_seed_mode.currentData() or "auto")
        if mode == "manual":
            self._session_seed_value.setEnabled(False)
            self._session_seed_value.setPlaceholderText(
                "Manual mode uses Trial schedule tab for per-slot exits."
            )
        elif mode == "legacy":
            self._session_seed_value.setEnabled(True)
            self._session_seed_value.setPlaceholderText("Path to legacy .h5 to replay exits")
        else:
            self._session_seed_value.setEnabled(True)
            self._session_seed_value.setPlaceholderText("Integer seed (blank = deterministic from Session ID)")
        if hasattr(self, "_schedule_seed_mode_hint"):
            self._refresh_trial_schedule_tab()

    def _on_browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Output folder")
        if path:
            self._output_dir_edit.setText(path)

    def _sync_track_enable_sleap_widget(self, *_args) -> None:
        has_path = bool((self._sleap_model_path_edit.text() or "").strip())
        self._track_enable_sleap_cb.setEnabled(has_path)

    def _on_browse_sleap_model(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "SLEAP model directory")
        if path:
            self._sleap_model_path_edit.setText(path)

    def _on_vast_preview_set_center_clicked_changed(self, state: int) -> None:
        self._config.preview_set_center_from_next_click = state == Qt.CheckState.Checked.value

    def _on_ram_preview_set_center_clicked_changed(self, state: int) -> None:
        self._config.preview_set_center_from_next_click = state == Qt.CheckState.Checked.value

    def _on_fallback_range_from_click_changed(self, state: int) -> None:
        ft = self._config.fallback_tracking
        ft.range_from_next_click = state == Qt.CheckState.Checked.value

    def _on_fallback_range_pick_delta_changed(self, value: int) -> None:
        self._config.fallback_tracking.range_pick_delta = max(0, int(value))

    def _on_fallback_range_pick_half_changed(self, value: int) -> None:
        self._config.fallback_tracking.range_pick_half = max(0, int(value))

    def _animals_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self._animals_table = QTableWidget()
        self._animals_table.setColumnCount(8)
        self._animals_table.setHorizontalHeaderLabels(
            [
                "Animal ID",
                "Sex",
                "Strain",
                "Treatment",
                "Drug",
                "Experiment",
                "Researcher",
                "Notes",
            ]
        )
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
        self._track_enable_backup_cb = QCheckBox("Enable backup tracking")
        self._track_enable_backup_cb.setToolTip("Adaptive-threshold blob tracker (in-range intensity).")
        options_ly.addWidget(self._track_enable_backup_cb)
        self._track_enable_sleap_cb = QCheckBox("Enable SLEAP tracking")
        self._track_enable_sleap_cb.setToolTip("Requires a SLEAP model directory below. When off, only backup runs if enabled.")
        options_ly.addWidget(self._track_enable_sleap_cb)
        self._track_exit_either_success_cb = QCheckBox("Use either success condition")
        self._track_exit_either_success_cb.setToolTip(
            "When enabled, a trial succeeds if either the SLEAP exit rule (min keypoints in exit zone) "
            "or the fallback rule (blob overlap with exit, or track point in exit if no blob) is satisfied, "
            "no matter which source is primary for the overlay."
        )
        options_ly.addWidget(self._track_exit_either_success_cb)
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
        pick_row = QHBoxLayout()
        self._fallback_range_from_next_click_cb = QCheckBox("Set backup range from next click")
        self._fallback_range_from_next_click_cb.setToolTip(
            "Next click on preview samples a small neighborhood and sets Range low/high below."
        )
        self._fallback_range_from_next_click_cb.stateChanged.connect(
            self._on_fallback_range_from_click_changed
        )
        pick_row.addWidget(self._fallback_range_from_next_click_cb)
        pick_row.addWidget(QLabel("±δ"))
        self._fallback_range_pick_delta_spin = QSpinBox()
        self._fallback_range_pick_delta_spin.setRange(0, 80)
        self._fallback_range_pick_delta_spin.setToolTip(
            "Half-width added to neighborhood min/max for backup range."
        )
        self._fallback_range_pick_delta_spin.valueChanged.connect(
            self._on_fallback_range_pick_delta_changed
        )
        pick_row.addWidget(self._fallback_range_pick_delta_spin)
        pick_row.addWidget(QLabel("nbhd"))
        self._fallback_range_pick_half_spin = QSpinBox()
        self._fallback_range_pick_half_spin.setRange(0, 15)
        self._fallback_range_pick_half_spin.setToolTip(
            "Neighborhood half-size in pixels (patch side = 2×nbhd+1)."
        )
        self._fallback_range_pick_half_spin.valueChanged.connect(
            self._on_fallback_range_pick_half_changed
        )
        pick_row.addWidget(self._fallback_range_pick_half_spin)
        pick_row.addStretch()
        f.addRow("Range from click:", pick_row)
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
        self._fallback_exit_blob_overlap_pct = QDoubleSpinBox()
        self._fallback_exit_blob_overlap_pct.setRange(0.0, 100.0)
        self._fallback_exit_blob_overlap_pct.setDecimals(1)
        self._fallback_exit_blob_overlap_pct.setSuffix(" %")
        self._fallback_exit_blob_overlap_pct.setValue(15.0)
        self._fallback_exit_blob_overlap_pct.setToolTip(
            "VAST success when using the fallback rule: minimum fraction of blob pixels overlapping the exit zone. "
            "If there is no blob mask, the track point in/out of exit is used instead."
        )
        f.addRow("Exit success blob overlap:", self._fallback_exit_blob_overlap_pct)
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
        self._sleap_model_path_edit.textChanged.connect(self._sync_track_enable_sleap_widget)
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
        self._fallback_node_max_jump.setToolTip(
            "SLEAP nodes: invalidate a node if it moves more than this (px) from the last accepted position. 0 = off."
        )
        sleap_f.addRow("Node max jump (px, 0=off):", self._fallback_node_max_jump)
        self._node_jump_confirm_frames = QSpinBox()
        self._node_jump_confirm_frames.setRange(1, 30)
        self._node_jump_confirm_frames.setValue(2)
        self._node_jump_confirm_frames.setToolTip(
            "Per-node: if a node stays beyond node max jump for this many frames in a row, reset all node jump "
            "state from the current pose (like Apply). 1 = reset on first over-threshold frame. 2+ ignores "
            "single-frame spikes. Also resets on virtual loop, Apply, flip image, and SLEAP↔fallback switch."
        )
        sleap_f.addRow("Node jump confirm (frames):", self._node_jump_confirm_frames)
        self._sleap_exit_min_keypoints = QSpinBox()
        self._sleap_exit_min_keypoints.setRange(1, 64)
        self._sleap_exit_min_keypoints.setValue(2)
        self._sleap_exit_min_keypoints.setToolTip(
            "VAST success when using the SLEAP rule: require at least this many valid keypoints inside the exit zone."
        )
        sleap_f.addRow("Exit success min keypoints:", self._sleap_exit_min_keypoints)
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
        if self._task_mode == "ram" and isinstance(c, RadialArmControllerConfig):
            ram = c.radial_arm
            template = ram.template
            calibration = ram.calibration
            self._ram_center_midedge_cm.setValue(template.center_midedge_to_midedge_cm)
            self._ram_arm_length_cm.setValue(template.arm_length_cm)
            self._ram_arm_width_cm.setValue(template.arm_width_cm)
            self._ram_arm_split_cm.setValue(template.arm_split_cm)
            self._ram_hole_radius_cm.setValue(template.hole_radius_cm)
            self._ram_hole_inset_cm.setValue(template.hole_inset_from_arm_end_cm)
            self._ram_template_center_x.setValue(calibration.template_center_x_px)
            self._ram_template_center_y.setValue(calibration.template_center_y_px)
            self._ram_template_rotation_deg.setValue(calibration.template_rotation_deg)
            self._ram_apothem_px.setValue(calibration.apothem_px)
            self._ram_tracking_mask_margin_px.setValue(
                int(round(calibration.tracking_mask_margin_px))
            )
            self._update_ram_px_per_cm_label()
            self._ram_edit_region_name.setText(calibration.edit_region_name)
            self._ram_stimulus_enabled.setChecked(ram.stimulus_enabled)
            self._ram_speaker_device_name.setText(ram.speaker_device_name)
            self._ram_speaker_volume_pct.setValue(ram.speaker_volume_pct)
            self._ram_stimulus_frequency_hz.setValue(ram.stimulus_frequency_hz)
        if isinstance(c, VastControllerConfig):
            arena = c.arena
            unit = arena.diameter_display_unit or "ft"
            if unit == "m":
                self._arena_diameter_value.setValue(arena.diameter_m)
            else:
                self._arena_diameter_value.setValue(arena.diameter_ft)
            idx = self._arena_diameter_unit.findData(unit)
            if idx >= 0:
                self._arena_diameter_unit.setCurrentIndex(idx)
            self._arena_radius_px.setValue(int(arena.radius_px))
            self._arena_tracking_radius_px.setValue(int(arena.tracking_radius_px))
            self._arena_center_pct.setValue(arena.center_pct)
            self._arena_exit_radius_cm.setValue(arena.exit_radius_cm)
            self._arena_center_x.setValue(arena.arena_center_x_px)
            self._arena_center_y.setValue(arena.arena_center_y_px)
            self._update_arena_px_per_cm_label()
            exit_angles = c.exit_angles
            self._exit_n_angles.setValue(exit_angles.n_angles)
            self._exit_offset_deg.setValue(exit_angles.offset_deg)
            self._exit_step_deg.setValue(exit_angles.step_deg)
            stimulus = c.stimulus
            self._stimulus_min_at_exit.setChecked(stimulus.min_at_exit)
            self._stimulus_min_duty.setValue(stimulus.min_duty_pct)
            self._stimulus_max_duty.setValue(stimulus.max_duty_pct)
            self._hab_duty.setValue(c.hab_training_duty_pct)
            self._wait_not_center_duty.setValue(c.wait_not_center_duty_pct)
            phase_value = self._task_spec.get_phase_value(c)
            idx = self._phase_combo.findData(phase_value)
            if idx >= 0:
                self._phase_combo.setCurrentIndex(idx)
            elif self._phase_combo.count() > 0:
                self._phase_combo.setCurrentIndex(0)
        sess = c.session
        self._session_num_animals.setValue(sess.num_animals)
        self._session_num_trials.setValue(sess.num_trials)
        self._session_max_trial_s.setValue(sess.max_trial_duration_s)
        self._session_iti_s.setValue(sess.iti_s)
        self._virtual_duration_override_s.setValue(
            float(getattr(c, "virtual_duration_override_s", 0.0) or 0.0)
        )
        seed_mode = str(getattr(sess, "seed_mode", "auto") or "auto")
        idx_seed_mode = self._session_seed_mode.findData(seed_mode)
        self._session_seed_mode.setCurrentIndex(idx_seed_mode if idx_seed_mode >= 0 else 0)
        if seed_mode == "legacy":
            self._session_seed_value.setText(str(sess.seed_legacy_source or ""))
        elif seed_mode == "manual":
            self._session_seed_value.setText("")
        else:
            self._session_seed_value.setText(
                "" if sess.seed_auto_value is None else str(int(sess.seed_auto_value))
            )
        self._sync_seed_value_widget_state()
        self._output_dir_edit.setText(c.output_dir or "")
        self._h5_filename_edit.setText(c.h5_filename or "trials.h5")
        parent = self.parent()
        if parent is not None and hasattr(parent, "_session_id_edit"):
            self._session_id_edit.setText((parent._session_id_edit.text() or "").strip())
        mode_value = self._task_spec.get_mode_value(c)
        idx = self._mode_combo.findData(mode_value)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        elif self._mode_combo.count() > 0:
            self._mode_combo.setCurrentIndex(0)
        # Animals table
        self._animals_table.setRowCount(max(len(sess.animals), 1))
        for i, animal in enumerate(sess.animals):
            self._animals_table.setItem(i, 0, QTableWidgetItem(animal.animal_id or ""))
            self._animals_table.setItem(i, 1, QTableWidgetItem(animal.sex or ""))
            self._animals_table.setItem(i, 2, QTableWidgetItem(animal.strain or ""))
            self._animals_table.setItem(i, 3, QTableWidgetItem(animal.tx or ""))
            self._animals_table.setItem(i, 4, QTableWidgetItem(animal.drug or ""))
            self._animals_table.setItem(i, 5, QTableWidgetItem(animal.experiment or ""))
            self._animals_table.setItem(i, 6, QTableWidgetItem(animal.researcher or ""))
            self._animals_table.setItem(i, 7, QTableWidgetItem(animal.notes or ""))
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
        self._sync_fallback_range_pick_widgets_from_config()
        self._fallback_node_max_jump.setValue(getattr(ft, "node_max_jump_px", 0.0))
        self._node_jump_confirm_frames.setValue(max(1, int(getattr(ft, "node_jump_confirm_frames", 2))))
        self._fallback_min_sleap_nodes.setValue(getattr(ft, "min_sleap_nodes", 1))
        self._fallback_show_blob_cb.setChecked(getattr(ft, "show_blob_overlay", True))
        self._fallback_max_contours.setValue(getattr(ft, "max_contours", 0))
        # Tracking options and SLEAP path
        self._track_show_cb.setChecked(getattr(c, "track_show", True))
        self._track_async_cb.setChecked(getattr(c, "track_async", False))
        self._track_enable_backup_cb.setChecked(getattr(c, "track_enable_backup", True))
        self._track_enable_sleap_cb.setChecked(getattr(c, "track_enable_sleap", True))
        self._sync_track_enable_sleap_widget()
        self._track_exit_either_success_cb.setChecked(getattr(c, "track_exit_either_success", False))
        self._sleap_model_path_edit.setText(getattr(c, "sleap_model_path", "") or "")
        # SLEAP
        self._sleap_confidence_pct.setValue(getattr(c, "sleap_confidence_pct", 50))
        self._sleap_every_n.setValue(max(1, min(5, getattr(c, "sleap_every_n", 1))))
        self._sleap_exit_min_keypoints.setValue(max(1, int(getattr(c, "sleap_exit_min_keypoints", 2))))
        self._fallback_exit_blob_overlap_pct.setValue(max(0.0, min(100.0, float(getattr(c, "fallback_exit_blob_overlap_pct", 15.0)))))
        self.sync_preview_center_checkbox_from_config()
        self._refresh_trial_schedule_tab()

    def _write_to_config(self) -> None:
        c = self._config
        if self._task_mode == "ram" and isinstance(c, RadialArmControllerConfig):
            ram = c.radial_arm
            ram.template.center_midedge_to_midedge_cm = self._ram_center_midedge_cm.value()
            ram.template.arm_length_cm = self._ram_arm_length_cm.value()
            ram.template.arm_width_cm = self._ram_arm_width_cm.value()
            ram.template.arm_split_cm = self._ram_arm_split_cm.value()
            ram.template.hole_radius_cm = self._ram_hole_radius_cm.value()
            ram.template.hole_inset_from_arm_end_cm = self._ram_hole_inset_cm.value()
            ram.calibration.template_center_x_px = self._ram_template_center_x.value()
            ram.calibration.template_center_y_px = self._ram_template_center_y.value()
            ram.calibration.template_rotation_deg = self._ram_template_rotation_deg.value()
            ram.calibration.apothem_px = self._ram_apothem_px.value()
            ram.calibration.tracking_mask_margin_px = float(
                self._ram_tracking_mask_margin_px.value()
            )
            sync_ram_px_per_cm(ram)
            ram.calibration.edit_region_name = self._ram_edit_region_name.text().strip()
            ram.stimulus_enabled = self._ram_stimulus_enabled.isChecked()
            ram.speaker_device_name = self._ram_speaker_device_name.text().strip()
            ram.speaker_volume_pct = self._ram_speaker_volume_pct.value()
            ram.stimulus_frequency_hz = self._ram_stimulus_frequency_hz.value()
        if isinstance(c, VastControllerConfig):
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
            c.hab_training_duty_pct = self._hab_duty.value()
            c.wait_not_center_duty_pct = self._wait_not_center_duty.value()
        n_exits = max(1, int(self._task_spec.get_num_exits(c)))
        default_idx = max(
            0,
            min(
                n_exits - 1,
                int(self._schedule_default_exit_idx.value()) - 1,
            ),
        )
        if isinstance(c, VastControllerConfig):
            c.exit_angles.default_manual_exit_index = default_idx
        if self._task_mode == "ram" and isinstance(c, RadialArmControllerConfig):
            c.radial_arm.exit_arm_index = max(0, min(7, default_idx))
        p = self._phase_combo.currentData()
        if p is not None and self._task_spec.set_phase_value is not None:
            self._task_spec.set_phase_value(c, str(p))
        c.session.num_animals = self._session_num_animals.value()
        c.session.num_trials = self._session_num_trials.value()
        c.session.max_trial_duration_s = self._session_max_trial_s.value()
        c.session.iti_s = self._session_iti_s.value()
        c.virtual_duration_override_s = (
            self._virtual_duration_override_s.value()
            if self._virtual_duration_override_s.value() > 0.0
            else None
        )
        seed_mode = str(self._session_seed_mode.currentData() or "auto")
        c.session.seed_mode = seed_mode if seed_mode in ("auto", "legacy", "manual") else "auto"
        c.session.seed_auto_value = None
        c.session.seed_legacy_source = None
        if c.session.seed_mode == "legacy":
            c.session.seed_legacy_source = (
                self._session_seed_value.text().strip() or None
            )
        elif c.session.seed_mode == "auto":
            c.session.seed_auto_value = _parse_seed_auto_value(
                self._session_seed_value.text()
            )
        c.output_dir = self._output_dir_edit.text().strip() or None
        c.h5_filename = self._h5_filename_edit.text().strip() or "trials.h5"
        m = self._mode_combo.currentData()
        if m is not None:
            self._task_spec.set_mode_value(c, str(m))
        # Animals
        rows = self._animals_table.rowCount()
        c.session.animals = []
        for i in range(rows):
            id_item = self._animals_table.item(i, 0)
            sex_item = self._animals_table.item(i, 1)
            strain_item = self._animals_table.item(i, 2)
            tx_item = self._animals_table.item(i, 3)
            drug_item = self._animals_table.item(i, 4)
            experiment_item = self._animals_table.item(i, 5)
            researcher_item = self._animals_table.item(i, 6)
            notes_item = self._animals_table.item(i, 7)
            aid = (id_item.text() or "").strip() if id_item else ""
            if not aid and i >= c.session.num_animals:
                continue
            c.session.animals.append(AnimalInfo(
                animal_id=aid or str(1000 + i),
                tx=(tx_item.text() or "").strip() or None if tx_item else None,
                strain=(strain_item.text() or "").strip() or None if strain_item else None,
                sex=(sex_item.text() or "").strip() or None if sex_item else None,
                drug=(drug_item.text() or "").strip() or None if drug_item else None,
                experiment=(experiment_item.text() or "").strip() or None
                if experiment_item
                else None,
                researcher=(researcher_item.text() or "").strip() or None
                if researcher_item
                else None,
                notes=(notes_item.text() or "").strip() or None if notes_item else None,
            ))
        c.session.ensure_animals()
        if c.session.seed_mode == "manual":
            ensure_exit_schedule_indices_length(
                c.session,
                n_exits=n_exits,
                default_exit_index=default_idx,
            )
            total = max(0, c.session.num_animals * c.session.num_trials)
            out: list[int] = []
            for row in range(total):
                it = self._schedule_table.item(row, 3)
                raw = (it.text() if it is not None else str(default_idx + 1)).strip()
                try:
                    v1 = int(raw)
                except ValueError:
                    v1 = default_idx + 1
                v1 = max(1, min(n_exits, v1))
                out.append(v1 - 1)
            c.session.exit_schedule_indices = out
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
        ft.range_from_next_click = self._fallback_range_from_next_click_cb.isChecked()
        ft.range_pick_delta = max(0, self._fallback_range_pick_delta_spin.value())
        ft.range_pick_half = max(0, self._fallback_range_pick_half_spin.value())
        ft.node_max_jump_px = self._fallback_node_max_jump.value()
        ft.node_jump_confirm_frames = max(1, self._node_jump_confirm_frames.value())
        ft.min_sleap_nodes = self._fallback_min_sleap_nodes.value()
        ft.show_blob_overlay = self._fallback_show_blob_cb.isChecked()
        ft.max_contours = max(0, self._fallback_max_contours.value())
        # Tracking options and SLEAP path
        c.track_show = self._track_show_cb.isChecked()
        c.track_async = self._track_async_cb.isChecked()
        path = (self._sleap_model_path_edit.text() or "").strip()
        c.track_enable_backup = self._track_enable_backup_cb.isChecked()
        c.track_enable_sleap = self._track_enable_sleap_cb.isChecked() if path else False
        adjusted = False
        if not c.track_enable_backup and not c.track_enable_sleap:
            c.track_enable_backup = True
            adjusted = True
        if c.track_enable_sleap and not path:
            c.track_enable_sleap = False
            adjusted = True
        if not c.track_enable_backup and not path:
            c.track_enable_backup = True
            adjusted = True
        c.track_exit_either_success = self._track_exit_either_success_cb.isChecked()
        c.sleap_model_path = path
        if adjusted:
            self._track_enable_backup_cb.setChecked(c.track_enable_backup)
            self._track_enable_sleap_cb.setChecked(c.track_enable_sleap)
            pw = self.parent()
            if pw is not None and hasattr(pw, "statusBar"):
                pw.statusBar().showMessage(
                    "Tracking: invalid backup/SLEAP combination — enabled backup tracking.",
                    5000,
                )
        # SLEAP
        c.sleap_confidence_pct = max(0, min(100, self._sleap_confidence_pct.value()))
        c.sleap_every_n = max(1, min(5, self._sleap_every_n.value()))
        c.sleap_exit_min_keypoints = max(1, self._sleap_exit_min_keypoints.value())
        c.fallback_exit_blob_overlap_pct = max(0.0, min(100.0, self._fallback_exit_blob_overlap_pct.value()))

    def _sync_fallback_range_pick_widgets_from_config(self) -> None:
        ft = getattr(self._config, "fallback_tracking", None) or FallbackTrackingConfig()
        self._fallback_range_from_next_click_cb.blockSignals(True)
        self._fallback_range_pick_delta_spin.blockSignals(True)
        self._fallback_range_pick_half_spin.blockSignals(True)
        try:
            self._fallback_range_from_next_click_cb.setChecked(
                bool(getattr(ft, "range_from_next_click", False))
            )
            self._fallback_range_pick_delta_spin.setValue(int(getattr(ft, "range_pick_delta", 12)))
            self._fallback_range_pick_half_spin.setValue(int(getattr(ft, "range_pick_half", 2)))
        finally:
            self._fallback_range_from_next_click_cb.blockSignals(False)
            self._fallback_range_pick_delta_spin.blockSignals(False)
            self._fallback_range_pick_half_spin.blockSignals(False)

    def sync_preview_center_checkbox_from_config(self) -> None:
        """Sync arena/RAM preview center-from-click checkboxes from ``self._config``."""
        v = bool(getattr(self._config, "preview_set_center_from_next_click", False))
        if hasattr(self, "_preview_set_center_from_click_cb"):
            self._preview_set_center_from_click_cb.blockSignals(True)
            try:
                self._preview_set_center_from_click_cb.setChecked(v)
            finally:
                self._preview_set_center_from_click_cb.blockSignals(False)
        if hasattr(self, "_ram_preview_set_center_from_click_cb"):
            self._ram_preview_set_center_from_click_cb.blockSignals(True)
            try:
                self._ram_preview_set_center_from_click_cb.setChecked(v)
            finally:
                self._ram_preview_set_center_from_click_cb.blockSignals(False)

    def sync_ram_template_center_widgets(self) -> None:
        """Update RAM template center X/Y fields from ``self._config``."""
        if not hasattr(self._config, "radial_arm"):
            return
        calib = self._config.radial_arm.calibration
        if hasattr(self, "_ram_template_center_x"):
            self._ram_template_center_x.blockSignals(True)
            try:
                self._ram_template_center_x.setValue(float(calib.template_center_x_px))
            finally:
                self._ram_template_center_x.blockSignals(False)
        if hasattr(self, "_ram_template_center_y"):
            self._ram_template_center_y.blockSignals(True)
            try:
                self._ram_template_center_y.setValue(float(calib.template_center_y_px))
            finally:
                self._ram_template_center_y.blockSignals(False)

    def sync_fallback_intensity_range_widgets(self) -> None:
        """Update Range low/high spinboxes from ``self._config`` (e.g. after eyedropper click on main window)."""
        ft = getattr(self._config, "fallback_tracking", None) or FallbackTrackingConfig()
        lo = int(getattr(ft, "range_low", 0))
        hi = int(getattr(ft, "range_high", 255))
        self._fallback_range_low.blockSignals(True)
        self._fallback_range_high.blockSignals(True)
        try:
            self._fallback_range_low.setValue(lo)
            self._fallback_range_high.setValue(hi)
        finally:
            self._fallback_range_low.blockSignals(False)
            self._fallback_range_high.blockSignals(False)
        self._sync_fallback_range_pick_widgets_from_config()

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
