from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from ..profile import load_analysis_profile, save_analysis_profile
from ..shared_config import AnalysisTrajectoryConfig
from ....pipeline.defaults import (
    JUMP_FILTER_LOOKAHEAD_FRAMES,
    MAX_MOVEMENT_PER_FRAME_CM,
    MOVEMENT_ENTRY_DEBOUNCE_FRAMES,
    MOVEMENT_EXIT_DEBOUNCE_FRAMES,
    MOVEMENT_INTER_BOUT_INTERVAL_FRAMES,
    MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES,
    MOVEMENT_START_THRESHOLD_M_PER_FRAME,
    MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
    MIN_MOVEMENT_BOUT_DURATION_FRAMES,
)
from .analysis_preview_model import (
    TrajectorySource,
    demo_source,
    list_trials_in_db,
    run_trajectory_preview,
    source_from_db,
)
from .profile_settings import (
    read_last_analysis_profile_path,
    save_last_analysis_profile_path,
)

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPen
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover
    raise


def _nice_map_scale_cm(target_cm: float) -> float:
    """Round ``target_cm`` up to a readable map scale (1–2–5–10 series)."""
    if not math.isfinite(target_cm) or target_cm <= 0:
        return 5.0
    exp = math.floor(math.log10(target_cm))
    unit = 10.0**exp
    t = target_cm / unit
    for f in (1.0, 2.0, 5.0, 10.0):
        if t <= f + 1e-9:
            return f * unit
    return 10.0 * unit


def _format_scale_label(cm: float) -> str:
    if cm >= 100.0:
        m = cm / 100.0
        if abs(m - round(m)) < 1e-6:
            return f"{int(round(m))} m"
        s = f"{m:.2f}".rstrip("0").rstrip(".")
        return f"{s} m"
    if abs(cm - round(cm)) < 1e-6:
        return f"{int(round(cm))} cm"
    s = f"{cm:.1f}".rstrip("0").rstrip(".")
    return f"{s} cm"


class TrajectoryPreviewWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._xy = np.empty((0, 2), dtype=float)
        self._bouts: list[dict] = []
        self._px_per_cm: float = 0.0
        self.setMinimumHeight(260)

    def set_data(
        self,
        xy: np.ndarray,
        bouts: list[dict],
        *,
        px_per_cm: float,
    ) -> None:
        self._xy = np.asarray(xy, dtype=float)
        self._bouts = list(bouts)
        self._px_per_cm = float(px_per_cm)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(22, 22, 22))
        if self._xy.shape[0] < 2:
            p.setPen(QColor(180, 180, 180))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No trajectory loaded")
            p.end()
            return
        x = self._xy[:, 0]
        y = self._xy[:, 1]
        finite = np.isfinite(x) & np.isfinite(y)
        if np.count_nonzero(finite) < 2:
            p.end()
            return
        xf = x[finite]
        yf = y[finite]
        min_x, max_x = float(np.min(xf)), float(np.max(xf))
        min_y, max_y = float(np.min(yf)), float(np.max(yf))
        span_x = max_x - min_x
        span_y = max_y - min_y
        if span_x <= 0:
            span_x = 1.0
        if span_y <= 0:
            span_y = 1.0
        margin = 18.0
        w = float(max(1, self.width()))
        h = float(max(1, self.height()))
        inner_w = max(1.0, w - 2.0 * margin)
        inner_h = max(1.0, h - 2.0 * margin)
        scale = min(inner_w / span_x, inner_h / span_y)
        plot_w = span_x * scale
        plot_h = span_y * scale
        left = margin + (inner_w - plot_w) * 0.5
        top = margin + (inner_h - plot_h) * 0.5

        def map_pt(px: float, py: float) -> tuple[float, float]:
            sx = left + (px - min_x) * scale
            sy = top + (max_y - py) * scale
            return sx, sy

        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Baseline trajectory.
        p.setPen(QPen(QColor(120, 120, 120), 1.0))
        last = None
        for i in range(self._xy.shape[0]):
            if not finite[i]:
                last = None
                continue
            pt = map_pt(float(x[i]), float(y[i]))
            if last is not None:
                p.drawLine(last[0], last[1], pt[0], pt[1])
            last = pt

        # Movement bouts in color.
        colors = [QColor(252, 141, 98), QColor(102, 194, 165), QColor(141, 160, 203)]
        for bi, bout in enumerate(self._bouts):
            c = colors[bi % len(colors)]
            pen = QPen(c, 2.2)
            p.setPen(pen)
            s = max(0, int(bout.get("start_frame", 0)))
            e = min(self._xy.shape[0] - 1, int(bout.get("end_frame", 0)))
            last = None
            for i in range(s, e + 1):
                if i >= self._xy.shape[0] or not finite[i]:
                    last = None
                    continue
                pt = map_pt(float(x[i]), float(y[i]))
                if last is not None:
                    p.drawLine(last[0], last[1], pt[0], pt[1])
                last = pt
            # Bout start/end markers.
            if 0 <= s < self._xy.shape[0] and finite[s]:
                sx, sy = map_pt(float(x[s]), float(y[s]))
                p.setPen(QPen(c, 2.0))
                p.drawEllipse(sx - 4.0, sy - 4.0, 8.0, 8.0)
            if 0 <= e < self._xy.shape[0] and finite[e]:
                ex, ey = map_pt(float(x[e]), float(y[e]))
                p.setPen(QPen(c, 2.0))
                p.drawLine(ex - 4.0, ey - 4.0, ex + 4.0, ey + 4.0)
                p.drawLine(ex - 4.0, ey + 4.0, ex + 4.0, ey - 4.0)

        # Map-style scale bar (true distance using px_per_cm and uniform scale).
        ppc = float(self._px_per_cm)
        if ppc > 0.0 and math.isfinite(scale) and scale > 0.0:
            pad_x = margin + 4.0
            target_cm = 0.18 * max(1e-6, min(span_x / ppc, span_y / ppc))
            nice_cm = _nice_map_scale_cm(target_cm)
            bar_data_px = nice_cm * ppc
            bar_screen = bar_data_px * scale
            max_bar = max(80.0, w - 2.0 * pad_x - 8.0)
            guard = 0
            while bar_screen > max_bar and guard < 12:
                nice_cm *= 0.5
                bar_data_px = nice_cm * ppc
                bar_screen = bar_data_px * scale
                guard += 1
            guard = 0
            while bar_screen < 36.0 and guard < 12:
                nice_cm = _nice_map_scale_cm(nice_cm * 1.51)
                bar_data_px = nice_cm * ppc
                bar_screen = bar_data_px * scale
                guard += 1
            text_gap = 4.0
            font = QFont()
            font.setPointSize(9)
            p.setFont(font)
            fm = p.fontMetrics()
            label = _format_scale_label(nice_cm)
            text_h = float(fm.height())
            y_base = h - margin - text_gap
            y_line = y_base - text_h * 0.35
            cap = 4.0
            x0 = pad_x
            x1 = pad_x + bar_screen
            p.setPen(QPen(QColor(235, 235, 235), 2.0))
            p.drawLine(x0, y_line, x1, y_line)
            p.drawLine(x0, y_line - cap, x0, y_line + cap)
            p.drawLine(x1, y_line - cap, x1, y_line + cap)
            p.setPen(QColor(210, 210, 210))
            p.drawText(
                int(x0 + bar_screen * 0.5 - fm.horizontalAdvance(label) * 0.5),
                int(y_base),
                label,
            )
        p.end()


class AnalysisSettingsDialog(QDialog):
    """Modeless analysis settings with trajectory preview."""

    def __init__(
        self,
        params: AnalysisTrajectoryConfig,
        parent: Optional[QWidget] = None,
        *,
        on_apply: Optional[Callable[[AnalysisTrajectoryConfig], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Analysis settings")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._params = AnalysisTrajectoryConfig(**vars(params))
        self._on_apply = on_apply
        self._source: TrajectorySource = demo_source()
        self._loaded_db_path: Optional[Path] = None
        self._loaded_key = None

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self._source_combo = QComboBox()
        self._source_combo.addItem("Demo trajectory")
        self._source_combo.setToolTip(
            "Trajectory shown in the preview: synthetic demo path, or x/y from a trial "
            "in an opened H5 (hybrid spot if present, else spot)."
        )
        _src_lbl = QLabel("Source:")
        _src_lbl.setToolTip(self._source_combo.toolTip())
        top.addWidget(_src_lbl)
        top.addWidget(self._source_combo)
        self._open_db_btn = QPushButton("Open H5…")
        self._open_db_btn.setToolTip(
            "Choose a trials database (.h5). Trials appear in the source list; FPS and "
            "px/cm come from the selected trial for preview scaling."
        )
        self._open_db_btn.clicked.connect(self._on_open_h5)
        top.addWidget(self._open_db_btn)
        top.addStretch()
        self._fps_label = QLabel("FPS source: demo (26.7)")
        self._fps_label.setToolTip(
            "Frames per second used to convert frame counts to seconds in summary stats "
            "(demo default or the trial’s fps attribute from H5)."
        )
        top.addWidget(self._fps_label)
        layout.addLayout(top)

        body = QHBoxLayout()
        left = QVBoxLayout()
        params_box = QGroupBox("Trace/trajectory (frame-based)")
        params_box.setToolTip(
            "All bout and jump settings are in frames; seconds in summaries use the source FPS. "
            "Apply saves these values into the acquisition config and trial HDF5 attributes."
        )
        form = QFormLayout(params_box)

        _tip_start = (
            "Instantaneous speed (meters per frame, after px/cm) must rise above this "
            "value to begin a movement bout. Uses median-smoothed speed; pair with a "
            "lower stop threshold for hysteresis."
        )
        self._start_thr = QDoubleSpinBox()
        self._start_thr.setDecimals(5)
        self._start_thr.setRange(0.0, 1.0)
        self._start_thr.setSingleStep(0.0005)
        self._start_thr.setToolTip(_tip_start)
        _lbl_start = QLabel("Movement start (m/frame):")
        _lbl_start.setToolTip(_tip_start)
        form.addRow(_lbl_start, self._start_thr)

        _tip_stop = (
            "After a bout has started, speed must stay below this m/frame level for "
            "the exit debounce window before the bout ends. Typically lower than the "
            "start threshold to avoid flicker."
        )
        self._stop_thr = QDoubleSpinBox()
        self._stop_thr.setDecimals(5)
        self._stop_thr.setRange(0.0, 1.0)
        self._stop_thr.setSingleStep(0.0005)
        self._stop_thr.setToolTip(_tip_stop)
        _lbl_stop = QLabel("Movement stop (m/frame):")
        _lbl_stop.setToolTip(_tip_stop)
        form.addRow(_lbl_stop, self._stop_thr)

        _tip_median = (
            "Odd-length median filter width (in frames) applied to per-frame speed "
            "before bout detection. Larger values smooth noise but slow response."
        )
        self._median_win = QSpinBox()
        self._median_win.setRange(1, 101)
        self._median_win.setToolTip(_tip_median)
        _lbl_median = QLabel("Speed median window (frames):")
        _lbl_median.setToolTip(_tip_median)
        form.addRow(_lbl_median, self._median_win)

        _tip_entry = (
            "Consecutive frames speed must stay above the start threshold before a "
            "new movement bout is declared (reduces spurious starts)."
        )
        self._entry_db = QSpinBox()
        self._entry_db.setRange(1, 200)
        self._entry_db.setToolTip(_tip_entry)
        _lbl_entry = QLabel("Entry debounce (frames):")
        _lbl_entry.setToolTip(_tip_entry)
        form.addRow(_lbl_entry, self._entry_db)

        _tip_exit = (
            "Consecutive frames speed must stay below the stop threshold before a "
            "bout ends (reduces spurious early endings)."
        )
        self._exit_db = QSpinBox()
        self._exit_db.setRange(1, 200)
        self._exit_db.setToolTip(_tip_exit)
        _lbl_exit = QLabel("Exit debounce (frames):")
        _lbl_exit.setToolTip(_tip_exit)
        form.addRow(_lbl_exit, self._exit_db)

        _tip_min_bout = (
            "Bouts shorter than this many frames are discarded after detection "
            "(post-processing merge of brief movements)."
        )
        self._min_bout = QSpinBox()
        self._min_bout.setRange(1, 2000)
        self._min_bout.setToolTip(_tip_min_bout)
        _lbl_min_bout = QLabel("Min bout duration (frames):")
        _lbl_min_bout.setToolTip(_tip_min_bout)
        form.addRow(_lbl_min_bout, self._min_bout)

        _tip_inter = (
            "Gap between two bouts (in frames) smaller than this is merged so nearby "
            "segments count as one bout. Set to 0 to disable merging by gap."
        )
        self._inter_gap = QSpinBox()
        self._inter_gap.setRange(0, 2000)
        self._inter_gap.setToolTip(_tip_inter)
        _lbl_inter = QLabel("Inter-bout interval (frames):")
        _lbl_inter.setToolTip(_tip_inter)
        form.addRow(_lbl_inter, self._inter_gap)

        _tip_jump = (
            "Maximum plausible step per frame for SLEAP-style traces (centimeters). "
            "Larger single-frame jumps are blanked unless confirmed by lookahead. "
            "Applied in the pipeline when loading SLEAP; preview uses the same rule."
        )
        self._max_jump_cm = QDoubleSpinBox()
        self._max_jump_cm.setDecimals(2)
        self._max_jump_cm.setRange(0.01, 500.0)
        self._max_jump_cm.setSingleStep(0.5)
        self._max_jump_cm.setToolTip(_tip_jump)
        _lbl_jump = QLabel("Jump filter max (cm/frame):")
        _lbl_jump.setToolTip(_tip_jump)
        form.addRow(_lbl_jump, self._max_jump_cm)

        _tip_look = (
            "After a large jump, how many following frames to check: if a later point "
            "lands near the jumped-to position within the max jump distance, the jump "
            "is kept as real motion; otherwise the frame is treated as an outlier."
        )
        self._jump_lookahead = QSpinBox()
        self._jump_lookahead.setRange(0, 60)
        self._jump_lookahead.setToolTip(_tip_look)
        _lbl_look = QLabel("Jump filter lookahead (frames):")
        _lbl_look.setToolTip(_tip_look)
        form.addRow(_lbl_look, self._jump_lookahead)

        _tip_px = (
            "Pixels per centimeter from the preview source (trial settings or demo). "
            "Used for speed/distance and jump filtering; not editable here."
        )
        self._pxcm_label = QLabel("—")
        self._pxcm_label.setToolTip(_tip_px)
        _lbl_px = QLabel("px/cm (read-only):")
        _lbl_px.setToolTip(_tip_px)
        form.addRow(_lbl_px, self._pxcm_label)
        left.addWidget(params_box)

        stats_box = QGroupBox("Summary")
        stats_box.setToolTip(
            "Metrics recomputed from the preview trajectory using current parameters "
            "(including jump filter) and the source FPS."
        )
        stats_grid = QGridLayout(stats_box)
        self._summary_bouts = QLabel("0")
        self._summary_dist = QLabel("0.00 m")
        self._summary_still = QLabel("0.00 s")
        self._summary_mean = QLabel("0.00 m/s")
        self._summary_max = QLabel("0.00 m/s")
        _sb_lbl0 = QLabel("Movement bouts:")
        _sb_lbl0.setToolTip("Count of movement bouts after debouncing, min duration, and gap merge.")
        stats_grid.addWidget(_sb_lbl0, 0, 0)
        self._summary_bouts.setToolTip(_sb_lbl0.toolTip())
        stats_grid.addWidget(self._summary_bouts, 0, 1)
        _sb_lbl1 = QLabel("Total distance:")
        _sb_lbl1.setToolTip("Path length along valid preview points, in meters (px/cm and frame gaps).")
        stats_grid.addWidget(_sb_lbl1, 1, 0)
        self._summary_dist.setToolTip(_sb_lbl1.toolTip())
        stats_grid.addWidget(self._summary_dist, 1, 1)
        _sb_lbl2 = QLabel("Time still:")
        _sb_lbl2.setToolTip(
            "Estimated time not in a movement bout (frames outside bouts / FPS)."
        )
        stats_grid.addWidget(_sb_lbl2, 2, 0)
        self._summary_still.setToolTip(_sb_lbl2.toolTip())
        stats_grid.addWidget(self._summary_still, 2, 1)
        _sb_lbl3 = QLabel("Mean speed:")
        _sb_lbl3.setToolTip("Mean speed over frames classified as moving (m/s).")
        stats_grid.addWidget(_sb_lbl3, 3, 0)
        self._summary_mean.setToolTip(_sb_lbl3.toolTip())
        stats_grid.addWidget(self._summary_mean, 3, 1)
        _sb_lbl4 = QLabel("Max speed:")
        _sb_lbl4.setToolTip("Peak instantaneous speed on moving frames (m/s).")
        stats_grid.addWidget(_sb_lbl4, 4, 0)
        self._summary_max.setToolTip(_sb_lbl4.toolTip())
        stats_grid.addWidget(self._summary_max, 4, 1)
        left.addWidget(stats_box)
        left.addStretch()
        body.addLayout(left, 0)

        self._preview = TrajectoryPreviewWidget(self)
        self._preview.setToolTip(
            "Trajectory with movement bouts in color; circles = bout starts, crosses = ends. "
            "Gray path is the full trace; colored segments match detected bouts. "
            "Uniform scaling preserves real-world aspect ratio; the scale bar shows true cm/m."
        )
        body.addWidget(self._preview, 1)
        layout.addLayout(body, 1)

        btns = QHBoxLayout()
        self._load_profile_btn = QPushButton("Load analysis profile…")
        self._save_profile_btn = QPushButton("Save analysis profile…")
        self._reset_btn = QPushButton("Reset to defaults")
        self._apply_btn = QPushButton("Apply")
        self._close_btn = QPushButton("Close")
        btns.addWidget(self._load_profile_btn)
        btns.addWidget(self._save_profile_btn)
        btns.addWidget(self._reset_btn)
        btns.addStretch()
        btns.addWidget(self._apply_btn)
        btns.addWidget(self._close_btn)
        layout.addLayout(btns)

        self._load_profile_btn.setToolTip(
            "Load analysis-only settings (movement + jump filter) from a JSON profile."
        )
        self._save_profile_btn.setToolTip(
            "Save current analysis parameters to a JSON file (separate from acquisition profile)."
        )
        self._reset_btn.setToolTip(
            "Restore all parameters to built-in pipeline defaults from defaults.py."
        )
        self._apply_btn.setToolTip(
            "Push these settings into the running acquisition config (used for new recordings "
            "and written trial attrs)."
        )
        self._close_btn.setToolTip("Close this window without applying (unless you clicked Apply).")

        self._load_profile_btn.clicked.connect(self._on_load_profile)
        self._save_profile_btn.clicked.connect(self._on_save_profile)
        self._reset_btn.clicked.connect(self._on_reset_defaults)
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        self._close_btn.clicked.connect(self.close)

        for w in (
            self._start_thr,
            self._stop_thr,
            self._median_win,
            self._entry_db,
            self._exit_db,
            self._min_bout,
            self._inter_gap,
            self._max_jump_cm,
            self._jump_lookahead,
        ):
            w.valueChanged.connect(self._refresh_preview)

        self._source_combo.currentIndexChanged.connect(self._on_source_index_changed)
        self._fill_from_params(self._params)
        self._refresh_preview()

    def _fill_from_params(self, p: AnalysisTrajectoryConfig) -> None:
        self._start_thr.setValue(float(p.movement_start_threshold_m_per_frame))
        self._stop_thr.setValue(float(p.movement_stop_threshold_m_per_frame))
        self._median_win.setValue(int(p.movement_speed_median_window_frames))
        self._entry_db.setValue(int(p.movement_entry_debounce_frames))
        self._exit_db.setValue(int(p.movement_exit_debounce_frames))
        self._min_bout.setValue(int(p.min_movement_bout_duration_frames))
        self._inter_gap.setValue(int(p.movement_inter_bout_interval_frames))
        self._max_jump_cm.setValue(float(p.max_movement_per_frame_cm))
        self._jump_lookahead.setValue(int(p.jump_filter_lookahead_frames))

    def set_params(self, params: AnalysisTrajectoryConfig) -> None:
        self._fill_from_params(params)
        self._refresh_preview()

    def _read_params(self) -> AnalysisTrajectoryConfig:
        return AnalysisTrajectoryConfig(
            movement_start_threshold_m_per_frame=float(self._start_thr.value()),
            movement_stop_threshold_m_per_frame=float(self._stop_thr.value()),
            movement_speed_median_window_frames=int(self._median_win.value()),
            movement_entry_debounce_frames=int(self._entry_db.value()),
            movement_exit_debounce_frames=int(self._exit_db.value()),
            min_movement_bout_duration_frames=int(self._min_bout.value()),
            movement_inter_bout_interval_frames=int(self._inter_gap.value()),
            max_movement_per_frame_cm=float(self._max_jump_cm.value()),
            jump_filter_lookahead_frames=int(self._jump_lookahead.value()),
        )

    def _refresh_preview(self) -> None:
        params = self._read_params()
        metrics, xy_plot = run_trajectory_preview(self._source, params)
        self._preview.set_data(
            xy_plot,
            metrics.movement_bouts,
            px_per_cm=float(self._source.px_per_cm),
        )
        self._summary_bouts.setText(str(metrics.n_movement_bouts))
        self._summary_dist.setText(f"{metrics.total_distance_m:.3f} m")
        self._summary_still.setText(f"{metrics.time_immobile_s:.2f} s")
        self._summary_mean.setText(f"{metrics.mean_speed_mps:.3f} m/s")
        self._summary_max.setText(f"{metrics.max_speed_mps:.3f} m/s")
        self._pxcm_label.setText(f"{self._source.px_per_cm:.4f}")
        if self._loaded_db_path is None:
            self._fps_label.setText(f"FPS source: demo ({self._source.fps:.3f})")
        else:
            self._fps_label.setText(f"FPS source: H5 trial ({self._source.fps:.3f})")

    def _on_source_index_changed(self, idx: int) -> None:
        if idx <= 0:
            self._source = demo_source()
            self._refresh_preview()
            return
        key = self._source_combo.itemData(idx)
        if self._loaded_db_path is None or key is None:
            return
        src = source_from_db(self._loaded_db_path, key)
        if src is not None:
            self._source = src
            self._loaded_key = key
        self._refresh_preview()

    def _on_open_h5(self) -> None:
        start_dir = ""
        if self._loaded_db_path is not None:
            start_dir = str(self._loaded_db_path.parent)
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Select analysis H5", start_dir, "H5 (*.h5 *.hdf5);;All (*)"
        )
        if not path_str:
            return
        p = Path(path_str)
        keys = list_trials_in_db(p)
        self._loaded_db_path = p
        self._source_combo.blockSignals(True)
        self._source_combo.clear()
        self._source_combo.addItem("Demo trajectory")
        for k in keys:
            self._source_combo.addItem(f"{k.animal_id}/{k.session}/{k.trial}", k)
        self._source_combo.blockSignals(False)
        if len(keys) > 0:
            self._source_combo.setCurrentIndex(1)
            src = source_from_db(p, keys[0])
            if src is not None:
                self._source = src
                self._loaded_key = keys[0]
        else:
            self._source_combo.setCurrentIndex(0)
            self._source = demo_source()
        self._refresh_preview()

    def _on_reset_defaults(self) -> None:
        self._fill_from_params(
            AnalysisTrajectoryConfig(
                movement_start_threshold_m_per_frame=MOVEMENT_START_THRESHOLD_M_PER_FRAME,
                movement_stop_threshold_m_per_frame=MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
                movement_speed_median_window_frames=MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES,
                movement_entry_debounce_frames=MOVEMENT_ENTRY_DEBOUNCE_FRAMES,
                movement_exit_debounce_frames=MOVEMENT_EXIT_DEBOUNCE_FRAMES,
                min_movement_bout_duration_frames=MIN_MOVEMENT_BOUT_DURATION_FRAMES,
                movement_inter_bout_interval_frames=MOVEMENT_INTER_BOUT_INTERVAL_FRAMES,
                max_movement_per_frame_cm=MAX_MOVEMENT_PER_FRAME_CM,
                jump_filter_lookahead_frames=JUMP_FILTER_LOOKAHEAD_FRAMES,
            )
        )
        self._refresh_preview()

    def _on_apply_clicked(self) -> None:
        if self._on_apply is not None:
            self._on_apply(self._read_params())

    def _on_save_profile(self) -> None:
        default_path = read_last_analysis_profile_path()
        default_dir = str(default_path.parent) if default_path is not None else ""
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save analysis profile",
            default_dir,
            "JSON (*.json);;All (*)",
        )
        if not path_str:
            return
        p = Path(path_str)
        save_analysis_profile(analysis_trajectory=self._read_params(), path=p)
        save_last_analysis_profile_path(p)

    def _on_load_profile(self) -> None:
        default_path = read_last_analysis_profile_path()
        default_dir = str(default_path.parent) if default_path is not None else ""
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Load analysis profile",
            default_dir,
            "JSON (*.json);;All (*)",
        )
        if not path_str:
            return
        p = Path(path_str)
        params = load_analysis_profile(p)
        self._fill_from_params(params)
        save_last_analysis_profile_path(p)
        self._refresh_preview()
