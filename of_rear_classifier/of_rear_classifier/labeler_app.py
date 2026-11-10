"""OF rearing syllable labeler — PySide6 (Goal B / multi-scorer).

Timeline UX
-----------
**Overview + detail** (DAW / NLE style — the “window over the timeline”):

- Top overview: whole session compressed to widget width; yellow box = viewport
- Detail strips: only the viewport (readable syllable/label structure)
- Click overview to jump · click detail to scrub · wheel pan · Ctrl+wheel zoom

Never sizes the window to 1 px/frame (that was the horizontal stretch bug).
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

try:
    from PySide6.QtCore import QEvent, Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QFileDialog,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PySide6 is required for the labeler app. From OpenEthoMaze root run:\n"
        "  uv sync --extra gui\n"
        "then relaunch with: uv run python of_rear_classifier/scripts/label_syllable_bouts.py …"
    ) from exc

from of_rear_classifier.export_sa_kpms import sa_h5_to_coordinates
from of_rear_classifier.label_store import (
    LABEL_CLASSES,
    add_manual_interval,
    bout_label_map,
    default_labels_path,
    labels_to_sturman_intervals,
    load_labels,
    migrate_bout_labels_into_store,
    sanitize_scorer,
    save_labels,
    upsert_syllable_label,
)
from of_rear_classifier.mlp_pred_io import discover_mlp_pred, load_mlp_pred_csv, mlp_strip_rgb
from of_rear_classifier.sa_kpms_skeleton import SA_KPMS_BODY_PARTS, SA_KPMS_EDGES
from of_rear_classifier.syllable_bouts import load_bout_table

LABEL_KEYS = {
    Qt.Key.Key_1: "Supported",
    Qt.Key.Key_2: "Unsupported",
    Qt.Key.Key_3: "Grooming",
    Qt.Key.Key_0: "None",
    Qt.Key.Key_N: "None",
}

_SYLL_PALETTE = np.array(
    [
        [31, 119, 180],
        [174, 199, 232],
        [255, 127, 14],
        [255, 187, 120],
        [44, 160, 44],
        [152, 223, 138],
        [214, 39, 40],
        [255, 152, 150],
        [148, 103, 189],
        [197, 176, 213],
        [140, 86, 75],
        [196, 156, 148],
        [227, 119, 194],
        [247, 182, 210],
        [127, 127, 127],
        [199, 199, 199],
        [188, 189, 34],
        [219, 219, 141],
        [23, 190, 207],
        [158, 218, 229],
    ],
    dtype=np.uint8,
)

_LABEL_RGB = {
    "Supported": (44, 160, 44),
    "Unsupported": (214, 39, 40),
    "Grooming": (255, 127, 14),
    "None": (127, 127, 127),
}

_HELP = (
    "1 Supported · 2 Unsupported · 3 Grooming · 0/n None  |  "
    "a/d or ←/→ bout · Shift+←/→ frame  |  space play (or next if replay off)  |  "
    "overview click = jump · detail click = scrub · wheel pan · Ctrl+wheel zoom  |  "
    "[ ] manual range · c/Esc clear  |  s save · e export · q quit"
)

# Layout (sibling folders under the Frailty data root):
#   <root>/Open Field - mp4/Test N.mp4
#   <root>/Open Field - kpms_sa13_per_video/Test N/model/syllable_bouts.csv
#   <root>/Open Field - superanimal/Test N_superanimal_….h5
#   <root>/base_transfer_pred/pred_Test N_majority.csv
#
# When a video is open, <root> = video.parent.parent (sibling of the mp4 folder).
# Fallback root is only for empty file-picker starts before a video is chosen.
_FALLBACK_DATA_ROOT = Path(r"D:\Open Field Frailty")
_SIBLING_MP4 = "Open Field - mp4"
_SIBLING_KPMS = "Open Field - kpms_sa13_per_video"
_SIBLING_SA = "Open Field - superanimal"
_SIBLING_MLP_PRED = "base_transfer_pred"

# Default detail window ≈ 45 s (readable bout structure without crushing the session).
_DEFAULT_VIEW_SEC = 45.0
_MIN_VIEW_FRAMES = 90
_MAX_VIEW_FRAC = 1.0


def _data_root_from_video(video: Path | None) -> Path:
    """Frailty root = parent of the mp4 folder (…/Open Field Frailty)."""
    if video is not None:
        return Path(video).resolve().parent.parent
    return _FALLBACK_DATA_ROOT


def _sibling_dir(video: Path | None, name: str) -> Path:
    return _data_root_from_video(video) / name


def _rgb_to_qpixmap(rgb: np.ndarray) -> QPixmap:
    h, w, _ = rgb.shape
    if h <= 0 or w <= 0:
        return QPixmap()
    buf = np.ascontiguousarray(rgb)
    qimg = QImage(buf.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def _downsample_span(src_1xt3: np.ndarray, t0: int, t1: int, width: int, height: int) -> np.ndarray:
    """Map frame span [t0, t1) → RGB image height×width (nearest)."""
    t0 = max(0, int(t0))
    t1 = max(t0 + 1, int(t1))
    width = max(int(width), 1)
    height = max(int(height), 1)
    span = src_1xt3[:, t0:t1, :]  # 1 x L x 3
    length = span.shape[1]
    xs = (np.arange(width) * length / width).astype(np.int64)
    xs = np.clip(xs, 0, length - 1)
    row = span[0, xs, :]  # W x 3
    return np.repeat(row[np.newaxis, :, :], height, axis=0)


def _guess_bouts_for_video(video: Path) -> Path | None:
    cand = _sibling_dir(video, _SIBLING_KPMS) / video.stem / "model" / "syllable_bouts.csv"
    return cand if cand.is_file() else None


def _guess_sa_h5_for_video(video: Path) -> Path | None:
    sa_root = _sibling_dir(video, _SIBLING_SA)
    if not sa_root.is_dir():
        return None
    hits = sorted(sa_root.glob(f"{video.stem}_superanimal*.h5"))
    return hits[0] if hits else None


def _mlp_pred_dir_for_video(video: Path | None) -> Path:
    return _sibling_dir(video, _SIBLING_MLP_PRED)


def _draw_pose_overlay(
    rgb: np.ndarray,
    xy: np.ndarray,
    *,
    part_index: dict[str, int],
    radius: int = 3,
) -> np.ndarray:
    """Draw SA-kpMS skeleton on an RGB frame (copy). ``xy`` is (K, 2)."""
    out = rgb.copy()
    for a, b in SA_KPMS_EDGES:
        ia, ib = part_index.get(a), part_index.get(b)
        if ia is None or ib is None:
            continue
        pa, pb = xy[ia], xy[ib]
        if not (np.isfinite(pa).all() and np.isfinite(pb).all()):
            continue
        p0 = (int(round(pa[0])), int(round(pa[1])))
        p1 = (int(round(pb[0])), int(round(pb[1])))
        cv2.line(out, p0, p1, (0, 255, 255), 1, cv2.LINE_AA)
    for k in range(xy.shape[0]):
        if not np.isfinite(xy[k]).all():
            continue
        pt = (int(round(xy[k, 0])), int(round(xy[k, 1])))
        cv2.circle(out, pt, radius, (255, 80, 80), -1, cv2.LINE_AA)
    return out


class TimelineStrip(QWidget):
    """Widget-width timeline (never 1 px/frame). Paints a downsampled frame span."""

    seekRequested = Signal(int)  # absolute frame
    panRequested = Signal(int)  # delta frames
    zoomRequested = Signal(float)  # factor >1 zoom in

    def __init__(self, *, height: int = 36, overview: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height + 4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("background:#111; border:1px solid #444;")
        self._overview = overview
        self._data: np.ndarray | None = None  # 1 x T x 3
        self._n_frames = 1
        self._view_t0 = 0
        self._view_t1 = 1
        self._playhead = 0
        self._viewport_t0 = 0  # overview only: yellow box
        self._viewport_t1 = 1

    def set_data(self, rgb_1xt3: np.ndarray, *, n_frames: int) -> None:
        self._data = np.ascontiguousarray(rgb_1xt3)
        self._n_frames = max(int(n_frames), 1)
        self.update()

    def set_view(self, t0: int, t1: int) -> None:
        self._view_t0 = int(t0)
        self._view_t1 = max(int(t1), self._view_t0 + 1)
        self.update()

    def set_playhead(self, frame: int) -> None:
        self._playhead = int(frame)
        self.update()

    def set_viewport_box(self, t0: int, t1: int) -> None:
        self._viewport_t0 = int(t0)
        self._viewport_t1 = max(int(t1), self._viewport_t0 + 1)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(17, 17, 17))
        if self._data is None or self.width() <= 1:
            return
        if self._overview:
            t0, t1 = 0, self._n_frames
        else:
            t0, t1 = self._view_t0, self._view_t1
        img = _downsample_span(self._data, t0, t1, self.width(), self.height())
        pix = _rgb_to_qpixmap(img)
        if not pix.isNull():
            p.drawPixmap(0, 0, pix)

        # playhead
        if self._overview:
            x = int(self._playhead / max(self._n_frames - 1, 1) * (self.width() - 1))
        else:
            span = max(t1 - t0, 1)
            x = int((self._playhead - t0) / span * (self.width() - 1))
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawLine(x, 0, x, self.height())

        # overview viewport box
        if self._overview:
            x0 = int(self._viewport_t0 / max(self._n_frames, 1) * self.width())
            x1 = int(self._viewport_t1 / max(self._n_frames, 1) * self.width())
            p.setPen(QPen(QColor(255, 220, 0), 2))
            p.setBrush(QColor(255, 220, 0, 40))
            p.drawRect(x0, 1, max(x1 - x0, 4), self.height() - 2)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # Pull focus out of the scorer line edit so keybinds work again.
        win = self.window()
        if win is not None:
            focus = win.focusWidget()
            if focus is not None and isinstance(focus, QLineEdit):
                focus.clearFocus()
            win.setFocus(Qt.FocusReason.MouseFocusReason)
        if self.width() <= 0:
            return
        x = float(event.position().x()) if hasattr(event, "position") else float(event.x())
        frac = min(max(x / self.width(), 0.0), 1.0)
        if self._overview:
            frame = int(frac * (self._n_frames - 1))
        else:
            span = max(self._view_t1 - self._view_t0, 1)
            frame = int(self._view_t0 + frac * span)
        self.seekRequested.emit(int(np.clip(frame, 0, self._n_frames - 1)))

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoomRequested.emit(0.85 if delta < 0 else 1.15)
        else:
            # pan by ~10% of current view
            step = max(int(0.1 * (self._view_t1 - self._view_t0)), 1)
            self.panRequested.emit(-step if delta > 0 else step)


class SyllableLabelerWindow(QMainWindow):
    def __init__(
        self,
        *,
        video: Path | None = None,
        bouts: Path | None = None,
        scorer: str | None = None,
        fps: float | None = None,
        export_intervals: Path | None = None,
        video_id: str | None = None,
        mlp_pred: Path | None = None,
        auto_load_mlp: bool = True,
    ) -> None:
        super().__init__()
        self.video_path = Path(video) if video else None
        self.bouts_path = Path(bouts) if bouts else None
        self.scorer = sanitize_scorer(scorer) if scorer else None
        self.fps_override = fps
        self.export_path = Path(export_intervals) if export_intervals else None
        self.video_id = video_id
        self._mlp_pred_arg = Path(mlp_pred) if mlp_pred else None
        self._auto_load_mlp = bool(auto_load_mlp)

        self.cap: cv2.VideoCapture | None = None
        self.bouts: pd.DataFrame | None = None
        self.labels: pd.DataFrame | None = None
        self.labels_path: Path | None = None
        self.fps = 30.0
        self.n_frames = 0
        self.bout_i = 0
        self.frame_i = 0
        self.dirty = False
        self.manual_t0: int | None = None
        self.manual_t1: int | None = None
        self._syll_base: np.ndarray | None = None
        self._lab_base: np.ndarray | None = None
        self.view_t0 = 0
        self.view_len = 1

        self._play_timer = QTimer(self)
        self._play_timer.timeout.connect(self._play_tick)
        self._play_end = 0
        self._video_pix: QPixmap | None = None
        self.pose_xy: np.ndarray | None = None  # (T, K, 2)
        self.pose_part_index: dict[str, int] = {}
        self.pose_h5_path: Path | None = None
        # Pose index relative to displayed video frame. +1 = draw next pose row
        # (fixes the common 1-frame overlay *lag* from OpenCV MP4 seek/decode).
        self._pose_frame_offset = 1
        self._cap_at: int | None = None  # last successfully decoded frame index
        self.mlp_labels: np.ndarray | None = None  # (T,) str
        self.mlp_scores: dict[str, np.ndarray] | None = None
        self.mlp_name: str | None = None
        self.mlp_pred_path: Path | None = None
        self._mlp_base: np.ndarray | None = None

        self._build_ui()
        self._bind_keys()

    def _no_focus_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setAutoDefault(False)
        btn.setDefault(False)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn

    def _no_focus_check(self, text: str, *, checked: bool = False) -> QCheckBox:
        box = QCheckBox(text)
        box.setChecked(checked)
        box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return box

    def _build_ui(self) -> None:
        self.setWindowTitle("of_rear syllable labeler")
        self.resize(1280, 860)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        toolbar = QHBoxLayout()
        self.btn_video = self._no_focus_button("Open video…")
        self.btn_bouts = self._no_focus_button("Open bouts…")
        self.btn_save = self._no_focus_button("Save")
        self.btn_export = self._no_focus_button("Export")
        self.scorer_edit = QLineEdit(self.scorer or "")
        self.scorer_edit.setPlaceholderText("scorer / initials")
        self.scorer_edit.setMaximumWidth(160)
        # Click to edit only — never tab/auto-focus, or keybinds die in the line edit.
        self.scorer_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.scorer_edit.editingFinished.connect(self._on_scorer_edit)
        self.scorer_edit.returnPressed.connect(self._release_scorer_focus)
        self.chk_replay = self._no_focus_check("Spacebar replay", checked=True)
        self.chk_replay.setToolTip(
            "On: Space always (re)plays the current bout.\n"
            "Off: first Space plays current; later Spaces advance to the next bout and play it."
        )
        self._space_should_advance = False

        self.chk_pose = self._no_focus_check("Pose overlay", checked=False)
        self.chk_pose.setToolTip("Draw SuperAnimal keypoints/skeleton on the video (loads SA H5).")
        self.chk_pose.toggled.connect(self._on_pose_toggled)
        self.chk_mlp_hud = self._no_focus_check("MLP HUD", checked=True)
        self.chk_mlp_hud.setToolTip("Show imported MLP class (+ softmax if present) on the video.")
        self.chk_mlp_hud.toggled.connect(lambda _c: self.refresh())
        self.btn_mlp = self._no_focus_button("Load MLP pred…")
        self.btn_mlp.setToolTip("Import pred_<video>_<Experimenter>.csv from davis_transfer run.")

        toolbar.addWidget(self.btn_video)
        toolbar.addWidget(self.btn_bouts)
        toolbar.addWidget(self.btn_mlp)
        toolbar.addWidget(QLabel("Scorer"))
        toolbar.addWidget(self.scorer_edit)
        toolbar.addWidget(self.chk_replay)
        toolbar.addWidget(self.chk_pose)
        toolbar.addWidget(self.chk_mlp_hud)
        toolbar.addStretch(1)
        toolbar.addWidget(self.btn_save)
        toolbar.addWidget(self.btn_export)
        root.addLayout(toolbar)

        self.help_label = QLabel(_HELP)
        self.help_label.setWordWrap(True)
        self.help_label.setStyleSheet(
            "color:#ddd; background:#222; padding:6px; font-family: Consolas, monospace;"
        )
        root.addWidget(self.help_label)

        self.video_label = QLabel("Open a video to begin")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumHeight(420)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_label.setStyleSheet("background:#000; color:#888;")
        self.video_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.video_label.setFocus()
        self.video_label.installEventFilter(self)
        root.addWidget(self.video_label, stretch=1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#eee; font-family: Consolas, monospace;")
        root.addWidget(self.status_label)

        root.addWidget(QLabel("overview (whole session) — yellow box = detail window"))
        self.overview = TimelineStrip(height=28, overview=True)
        self.overview.seekRequested.connect(self.seek_frame)
        root.addWidget(self.overview)

        root.addWidget(QLabel("detail · syllables (kpMS)"))
        self.detail_syll = TimelineStrip(height=40, overview=False)
        self.detail_syll.seekRequested.connect(self.seek_frame)
        self.detail_syll.panRequested.connect(self.pan_view)
        self.detail_syll.zoomRequested.connect(self.zoom_view)
        root.addWidget(self.detail_syll)

        root.addWidget(QLabel("detail · labels — cyan/magenta = pending manual [ ]"))
        self.detail_lab = TimelineStrip(height=40, overview=False)
        self.detail_lab.seekRequested.connect(self.seek_frame)
        self.detail_lab.panRequested.connect(self.pan_view)
        self.detail_lab.zoomRequested.connect(self.zoom_view)
        root.addWidget(self.detail_lab)

        self.mlp_strip_label = QLabel("detail · MLP (load pred CSV)")
        root.addWidget(self.mlp_strip_label)
        self.detail_mlp = TimelineStrip(height=36, overview=False)
        self.detail_mlp.seekRequested.connect(self.seek_frame)
        self.detail_mlp.panRequested.connect(self.pan_view)
        self.detail_mlp.zoomRequested.connect(self.zoom_view)
        root.addWidget(self.detail_mlp)

        self.btn_video.clicked.connect(self._pick_video)
        self.btn_bouts.clicked.connect(self._pick_bouts)
        self.btn_mlp.clicked.connect(self._pick_mlp_pred)
        self.btn_save.clicked.connect(self.save)
        self.btn_export.clicked.connect(self.export_intervals)

    def _scorer_capturing(self) -> bool:
        return self.scorer_edit.hasFocus()

    def _release_scorer_focus(self) -> None:
        self.scorer_edit.clearFocus()
        self.video_label.setFocus(Qt.FocusReason.OtherFocusReason)

    def _bind_keys(self) -> None:
        # ApplicationShortcut so Space/nav work even if a child widget had focus —
        # but never while the scorer field is actively being edited.
        sc = Qt.ShortcutContext.ApplicationShortcut

        def _unless_scorer(fn):
            def _wrap(*_a, **_k):
                if self._scorer_capturing():
                    return
                fn()

            return _wrap

        def _nav(delta: int) -> None:
            self.goto_bout(self.bout_i + delta)

        def _nudge(delta: int) -> None:
            self.nudge_frame(delta)

        def _label(name: str) -> None:
            self.apply_label(name)

        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=_unless_scorer(self.toggle_play), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_S), self, activated=_unless_scorer(self.save), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_E), self, activated=_unless_scorer(self.export_intervals), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_Q), self, activated=_unless_scorer(self.close), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_A), self, activated=_unless_scorer(lambda: _nav(-1)), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_D), self, activated=_unless_scorer(lambda: _nav(1)), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=_unless_scorer(lambda: _nav(-1)), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=_unless_scorer(lambda: _nav(1)), context=sc)
        QShortcut(
            QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_Left),
            self,
            activated=_unless_scorer(lambda: _nudge(-1)),
            context=sc,
        )
        QShortcut(
            QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_Right),
            self,
            activated=_unless_scorer(lambda: _nudge(1)),
            context=sc,
        )
        QShortcut(QKeySequence(Qt.Key.Key_1), self, activated=_unless_scorer(lambda: _label("Supported")), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_2), self, activated=_unless_scorer(lambda: _label("Unsupported")), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_3), self, activated=_unless_scorer(lambda: _label("Grooming")), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_0), self, activated=_unless_scorer(lambda: _label("None")), context=sc)
        QShortcut(QKeySequence(Qt.Key.Key_N), self, activated=_unless_scorer(lambda: _label("None")), context=sc)

    # ----- load -----

    def bootstrap(self) -> bool:
        if self.video_path is None or not self.video_path.is_file():
            mp4_start = _sibling_dir(None, _SIBLING_MP4)
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open OF video",
                str(mp4_start if mp4_start.is_dir() else Path.home()),
                "Video (*.mp4 *.avi *.mkv);;All (*.*)",
            )
            if not path:
                return False
            self.video_path = Path(path)
        if self.bouts_path is None or not self.bouts_path.is_file():
            guess = _guess_bouts_for_video(self.video_path)
            kpms_root = _sibling_dir(self.video_path, _SIBLING_KPMS)
            start = str(guess.parent) if guess else str(kpms_root if kpms_root.is_dir() else Path.home())
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open syllable_bouts.csv",
                start,
                "CSV (*.csv);;All (*.*)",
            )
            if not path:
                if guess is not None:
                    self.bouts_path = guess
                else:
                    return False
            else:
                self.bouts_path = Path(path)
        if not self.scorer:
            name, ok = QInputDialog.getText(self, "Scorer", "Initials / name for this session:", text="scorer")
            if not ok:
                return False
            self.scorer = sanitize_scorer(name)
            self.scorer_edit.setText(self.scorer)
        self.labels_path = default_labels_path(self.bouts_path, self.scorer)
        if self.export_path is None:
            self.export_path = self.bouts_path.parent / "labels" / f"{self.scorer}_sturman_intervals.csv"
        if self.video_id is None:
            self.video_id = self.video_path.stem
        try:
            self._load_session()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(exc))
            return False
        return True

    def _load_session(self) -> None:
        assert self.video_path and self.bouts_path and self.scorer
        self.bouts = load_bout_table(self.bouts_path)
        if self.bouts.empty:
            raise RuntimeError(f"empty bout table: {self.bouts_path}")
        self.labels_path = default_labels_path(self.bouts_path, self.scorer)
        self.labels = migrate_bout_labels_into_store(
            self.bouts_path, scorer=self.scorer, labels_path=self.labels_path
        )
        if self.export_path is None:
            self.export_path = self.bouts_path.parent / "labels" / f"{self.scorer}_sturman_intervals.csv"
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture(str(self.video_path))
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open video {self.video_path}")
        self._cap_at = None
        self.fps = float(self.fps_override) if self.fps_override else float(self.cap.get(cv2.CAP_PROP_FPS) or 30.0)
        self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or int(self.bouts["t1_frame"].max()) + 1)
        self.bout_i = 0
        self.frame_i = int(self.bouts.iloc[0]["t0_frame"])
        self.dirty = False
        self.manual_t0 = self.manual_t1 = None
        self.view_len = int(np.clip(self.fps * _DEFAULT_VIEW_SEC, _MIN_VIEW_FRAMES, self.n_frames))
        self._center_view_on_playhead()
        self._build_syllable_strip()
        self.pose_xy = None
        self.pose_part_index = {}
        self.pose_h5_path = _guess_sa_h5_for_video(self.video_path) if self.video_path else None
        if self.chk_pose.isChecked():
            self._ensure_pose_loaded()
        self._try_autoload_mlp()
        self.setWindowTitle(f"of_rear labeler — {self.video_id} [{self.scorer}]")
        self.refresh()
        self._release_scorer_focus()

    def _clear_mlp(self) -> None:
        self.mlp_labels = None
        self.mlp_scores = None
        self.mlp_name = None
        self.mlp_pred_path = None
        self._mlp_base = None
        self.mlp_strip_label.setText("detail · MLP (load pred CSV)")
        empty = np.full((1, max(self.n_frames, 1), 3), 16, dtype=np.uint8)
        self.detail_mlp.set_data(empty, n_frames=max(self.n_frames, 1))

    def _try_autoload_mlp(self) -> None:
        path = self._mlp_pred_arg
        if path is None and self._auto_load_mlp and self.video_id:
            path = discover_mlp_pred(
                self.video_id, pred_dir=_mlp_pred_dir_for_video(self.video_path)
            )
        if path is not None and path.is_file():
            self.load_mlp_pred(path)
        else:
            self._clear_mlp()

    def load_mlp_pred(self, path: Path | str) -> None:
        path = Path(path)
        data = load_mlp_pred_csv(path, n_frames=self.n_frames)
        self.mlp_labels = data["labels"]
        self.mlp_scores = data["scores"]
        self.mlp_name = str(data["experimenter"])
        self.mlp_pred_path = path
        self._mlp_base = mlp_strip_rgb(self.mlp_labels, label_rgb=_LABEL_RGB)
        self.mlp_strip_label.setText(f"detail · MLP←{self.mlp_name}  ({path.name})")
        score_note = " + softmax" if self.mlp_scores else " (hard labels only — re-run transfer for p_*)"
        print(f"MLP pred loaded {path} · {data['frames_in_csv']} rows{score_note}", flush=True)
        self.refresh()

    def _pick_mlp_pred(self) -> None:
        pred_dir = _mlp_pred_dir_for_video(self.video_path)
        start = str(pred_dir if pred_dir.is_dir() else Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open MLP pred CSV",
            start,
            "CSV (pred_*.csv);;All (*.*)",
        )
        if not path:
            return
        try:
            self.load_mlp_pred(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "MLP pred", f"Failed to load:\n{exc}")

    def _ensure_pose_loaded(self) -> bool:
        if self.pose_xy is not None:
            return True
        if self.video_path is None:
            return False
        if self.pose_h5_path is None or not self.pose_h5_path.is_file():
            self.pose_h5_path = _guess_sa_h5_for_video(self.video_path)
        if self.pose_h5_path is None or not self.pose_h5_path.is_file():
            sa_root = _sibling_dir(self.video_path, _SIBLING_SA)
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open SuperAnimal pose H5 for overlay",
                str(sa_root if sa_root.is_dir() else Path.home()),
                "H5 (*.h5);;All (*.*)",
            )
            if not path:
                return False
            self.pose_h5_path = Path(path)
        try:
            coords, _conf, parts = sa_h5_to_coordinates(
                self.pose_h5_path, body_parts=SA_KPMS_BODY_PARTS, likelihood_min=0.3
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Pose overlay", f"Failed to load pose:\n{exc}")
            return False
        self.pose_xy = np.asarray(coords, dtype=np.float32)
        self.pose_part_index = {name: i for i, name in enumerate(parts)}
        print(f"pose overlay loaded {self.pose_h5_path.name} T={self.pose_xy.shape[0]}", flush=True)
        return True

    def _on_pose_toggled(self, checked: bool) -> None:
        if checked and not self._ensure_pose_loaded():
            self.chk_pose.blockSignals(True)
            self.chk_pose.setChecked(False)
            self.chk_pose.blockSignals(False)
            return
        self.refresh()

    def _build_syllable_strip(self) -> None:
        assert self.bouts is not None
        t = max(self.n_frames, int(self.bouts["t1_frame"].max()) + 1)
        self.n_frames = t
        strip = np.full((1, t, 3), 20, dtype=np.uint8)
        t0s = self.bouts["t0_frame"].to_numpy(dtype=int)
        t1s = self.bouts["t1_frame"].to_numpy(dtype=int)
        sids = self.bouts["syllable_id"].to_numpy(dtype=int) % len(_SYLL_PALETTE)
        for t0, t1, sid in zip(t0s, t1s, sids, strict=True):
            strip[0, t0 : t1 + 1] = _SYLL_PALETTE[sid]
        self._syll_base = strip
        self._rebuild_label_base()

    def _rebuild_label_base(self) -> None:
        assert self.bouts is not None
        t = self.n_frames
        strip = np.full((1, t, 3), 16, dtype=np.uint8)
        bmap = bout_label_map(self.labels)
        t0s = self.bouts["t0_frame"].to_numpy(dtype=int)
        t1s = self.bouts["t1_frame"].to_numpy(dtype=int)
        bis = self.bouts["bout_index"].to_numpy(dtype=int)
        for t0, t1, bi in zip(t0s, t1s, bis, strict=True):
            lab = bmap.get(int(bi), "")
            if lab:
                strip[0, t0 : t1 + 1] = _LABEL_RGB.get(lab, (148, 103, 189))
        if self.labels is not None and not self.labels.empty:
            man = self.labels.loc[self.labels["source"] == "manual"]
            for _, row in man.iterrows():
                rgb = _LABEL_RGB.get(str(row["label"]), (148, 103, 189))
                strip[0, int(row["t0_frame"]) : int(row["t1_frame"]) + 1] = rgb
        if self.manual_t0 is not None and self.manual_t1 is not None:
            a, b = sorted((self.manual_t0, self.manual_t1))
            strip[0, a : b + 1] = (0, 200, 200)
        elif self.manual_t0 is not None:
            f = int(np.clip(self.manual_t0, 0, t - 1))
            strip[0, max(0, f - 1) : min(t, f + 2)] = (0, 255, 255)
        elif self.manual_t1 is not None:
            f = int(np.clip(self.manual_t1, 0, t - 1))
            strip[0, max(0, f - 1) : min(t, f + 2)] = (255, 0, 255)
        self._lab_base = strip

    # ----- viewport -----

    def _view_t1(self) -> int:
        return min(self.view_t0 + self.view_len, self.n_frames)

    def _center_view_on_playhead(self) -> None:
        half = self.view_len // 2
        self.view_t0 = int(np.clip(self.frame_i - half, 0, max(self.n_frames - self.view_len, 0)))

    def pan_view(self, delta_frames: int) -> None:
        self.view_t0 = int(np.clip(self.view_t0 + int(delta_frames), 0, max(self.n_frames - self.view_len, 0)))
        self._update_timelines()

    def zoom_view(self, factor: float) -> None:
        center = self.frame_i
        new_len = int(np.clip(self.view_len / factor, _MIN_VIEW_FRAMES, max(self.n_frames, _MIN_VIEW_FRAMES)))
        self.view_len = new_len
        self.view_t0 = int(np.clip(center - new_len // 2, 0, max(self.n_frames - self.view_len, 0)))
        self._update_timelines()

    # ----- render -----

    def _read_video_bgr(self, frame_idx: int) -> np.ndarray | None:
        """Decode absolute frame ``frame_idx`` (0-based). Prefer sequential read over seek."""
        if self.cap is None:
            return None
        frame_idx = int(max(0, frame_idx))
        # Sequential path (playback): avoid re-seek every tick — seek is where
        # FFMPEG/MSMF often slips by ±1 vs the pose H5 index.
        if self._cap_at is not None and frame_idx == self._cap_at + 1:
            ok, bgr = self.cap.read()
            if ok:
                self._cap_at = frame_idx
                return bgr
            self._cap_at = None
        if self._cap_at == frame_idx:
            # Re-show same frame: must re-seek; OpenCV has no reliable peek.
            self._cap_at = None
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, float(frame_idx))
        ok, bgr = self.cap.read()
        if not ok:
            self._cap_at = None
            return None
        self._cap_at = frame_idx
        return bgr

    def _show_frame(self) -> None:
        if self.cap is None:
            return
        bgr = self._read_video_bgr(self.frame_i)
        if bgr is None:
            self.video_label.setText(f"seek failed @ {self.frame_i}")
            return
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if self.chk_pose.isChecked() and self.pose_xy is not None:
            pose_i = int(self.frame_i) + int(self._pose_frame_offset)
            if 0 <= pose_i < self.pose_xy.shape[0]:
                rgb = _draw_pose_overlay(
                    rgb, self.pose_xy[pose_i], part_index=self.pose_part_index
                )
        if self.chk_mlp_hud.isChecked() and self.mlp_labels is not None:
            rgb = self._draw_mlp_hud(rgb)
        pix = _rgb_to_qpixmap(rgb)
        if pix.isNull():
            return
        self._video_pix = pix
        target = self.video_label.size()
        if target.width() < 2 or target.height() < 2:
            self.video_label.setPixmap(pix)
            return
        self.video_label.setPixmap(
            pix.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _mlp_status_at(self, frame: int) -> str:
        if self.mlp_labels is None:
            return ""
        f = int(np.clip(frame, 0, len(self.mlp_labels) - 1))
        lab = str(self.mlp_labels[f])
        bits = [f"MLP←{self.mlp_name}={lab}"]
        if self.mlp_scores:
            # show top class probability if available
            best_p = -1.0
            best_name = lab
            for name, arr in self.mlp_scores.items():
                v = float(arr[f]) if np.isfinite(arr[f]) else -1.0
                if v > best_p:
                    best_p, best_name = v, name
            if best_p >= 0:
                bits.append(f"p={best_p:.2f}({best_name})")
        return "  ·  " + " ".join(bits)

    def _draw_mlp_hud(self, rgb: np.ndarray) -> np.ndarray:
        assert self.mlp_labels is not None
        f = int(np.clip(self.frame_i, 0, len(self.mlp_labels) - 1))
        lab = str(self.mlp_labels[f])
        color = _LABEL_RGB.get(lab, (200, 200, 200))
        out = rgb.copy()
        text = f"MLP {self.mlp_name}: {lab}"
        if self.mlp_scores and lab in self.mlp_scores:
            p = self.mlp_scores[lab][f]
            if np.isfinite(p):
                text += f"  p={float(p):.2f}"
        cv2.rectangle(out, (8, 8), (8 + 12 + 9 * len(text), 40), (0, 0, 0), -1)
        cv2.putText(
            out,
            text,
            (14, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA,
        )
        return out

    def _status_text(self) -> str:
        if self.bouts is None:
            return ""
        row = self.bouts.iloc[self.bout_i]
        lab = bout_label_map(self.labels).get(int(row["bout_index"]), "") or "(unset)"
        man = ""
        if self.manual_t0 is not None or self.manual_t1 is not None:
            man = f"  |  manual [{self.manual_t0} … {self.manual_t1}]"
        dirty = " *" if self.dirty else ""
        view_sec = self.view_len / max(self.fps, 1.0)
        return (
            f"{self.video_id}  ·  scorer={self.scorer}{dirty}  ·  "
            f"bout {self.bout_i + 1}/{len(self.bouts)}  syll={int(row['syllable_id'])}  "
            f"frames {int(row['t0_frame'])}-{int(row['t1_frame'])}  "
            f"label={lab}  ·  frame={self.frame_i}  ·  "
            f"view {self.view_t0}-{self._view_t1()} (~{view_sec:.0f}s)"
            f"{self._mlp_status_at(self.frame_i)}{man}"
        )

    def _update_timelines(self) -> None:
        if self._syll_base is None or self._lab_base is None:
            return
        t0, t1 = self.view_t0, self._view_t1()
        strips = [
            (self.overview, self._syll_base),
            (self.detail_syll, self._syll_base),
            (self.detail_lab, self._lab_base),
        ]
        if self._mlp_base is not None:
            strips.append((self.detail_mlp, self._mlp_base))
        for strip, data in strips:
            strip.set_data(data, n_frames=self.n_frames)
            strip.set_view(t0, t1)
            strip.set_playhead(self.frame_i)
        self.overview.set_viewport_box(t0, t1)
        self.status_label.setText(self._status_text())

    def refresh(self, *, labels_changed: bool = False) -> None:
        if self.bouts is None:
            return
        if labels_changed or self._lab_base is None:
            self._rebuild_label_base()
        self._show_frame()
        self._update_timelines()

    # ----- navigation / labels -----

    def seek_frame(self, frame: int) -> None:
        if self.bouts is None:
            return
        self._play_timer.stop()
        self.frame_i = int(np.clip(frame, 0, max(self.n_frames - 1, 0)))
        self.bout_i = self._bout_index_at_frame(self.frame_i)
        self._space_should_advance = False
        # Keep playhead inside detail window; jump recenters if outside.
        if self.frame_i < self.view_t0 or self.frame_i >= self._view_t1():
            self._center_view_on_playhead()
        self.refresh()

    def nudge_frame(self, delta: int) -> None:
        """Single-frame scrub (Shift+←/→)."""
        self.seek_frame(self.frame_i + int(delta))

    def _bout_index_at_frame(self, frame: int) -> int:
        assert self.bouts is not None
        t0 = self.bouts["t0_frame"].to_numpy(dtype=int)
        t1 = self.bouts["t1_frame"].to_numpy(dtype=int)
        hits = np.flatnonzero((t0 <= frame) & (frame <= t1))
        if hits.size:
            return int(hits[0])
        return int(np.clip(np.searchsorted(t0, frame) - 1, 0, len(self.bouts) - 1))

    def goto_bout(self, i: int, *, from_space_advance: bool = False) -> None:
        if self.bouts is None:
            return
        self.bout_i = int(np.clip(i, 0, len(self.bouts) - 1))
        self.frame_i = int(self.bouts.iloc[self.bout_i]["t0_frame"])
        if not from_space_advance:
            self._space_should_advance = False
        self._center_view_on_playhead()
        self.refresh()

    def apply_label(self, label: str) -> None:
        if self.bouts is None or self.scorer is None:
            return
        if self.manual_t0 is not None and self.manual_t1 is not None:
            self.labels = add_manual_interval(
                self.labels,
                scorer=self.scorer,
                t0_frame=self.manual_t0,
                t1_frame=self.manual_t1,
                label=label,
            )
            self.manual_t0 = self.manual_t1 = None
            self.dirty = True
            self.refresh(labels_changed=True)
            return
        row = self.bouts.iloc[self.bout_i]
        self.labels = upsert_syllable_label(
            self.labels,
            scorer=self.scorer,
            bout_index=int(row["bout_index"]),
            syllable_id=int(row["syllable_id"]),
            t0_frame=int(row["t0_frame"]),
            t1_frame=int(row["t1_frame"]),
            label=label,
        )
        self.dirty = True
        self._rebuild_label_base()
        self.goto_bout(self.bout_i + 1)

    def save(self) -> None:
        if self.labels_path is None or self.labels is None:
            return
        # Don't steal focus from scorer field accidentally when shortcut fires mid-edit
        if self.scorer_edit.hasFocus():
            return
        save_labels(self.labels, self.labels_path)
        self.dirty = False
        self.status_label.setText(self._status_text() + f"  |  saved {self.labels_path.name}")
        print(f"saved {self.labels_path} ({len(self.labels)} intervals)", flush=True)

    def export_intervals(self) -> None:
        if self.export_path is None or self.video_id is None or self.scorer is None:
            return
        if self.scorer_edit.hasFocus():
            return
        if self.dirty:
            self.save()
        intervals = labels_to_sturman_intervals(
            self.labels, fps=self.fps, video_id=self.video_id, scorer=self.scorer
        )
        self.export_path.parent.mkdir(parents=True, exist_ok=True)
        intervals.to_csv(self.export_path, index=False)
        self.status_label.setText(self._status_text() + f"  |  exported {len(intervals)} intervals")
        print(f"exported {self.export_path} ({len(intervals)} rows)", flush=True)

    def toggle_play(self) -> None:
        if self.scorer_edit.hasFocus():
            return
        if self._play_timer.isActive():
            self._play_timer.stop()
            if not self.chk_replay.isChecked():
                self._space_should_advance = True
            return
        if self.chk_replay.isChecked():
            self._play_bout()
            return
        # Advance mode: first Space plays current; later Spaces go next then play.
        if self._space_should_advance:
            self.goto_bout(self.bout_i + 1, from_space_advance=True)
        self._play_bout()
        self._space_should_advance = True

    def _play_bout(self) -> None:
        if self.bouts is None:
            return
        row = self.bouts.iloc[self.bout_i]
        self.frame_i = int(row["t0_frame"])
        self._play_end = int(row["t1_frame"])
        if self.frame_i < self.view_t0 or self.frame_i >= self._view_t1():
            self._center_view_on_playhead()
        self._play_timer.start(max(int(1000 / max(self.fps, 1.0)), 1))
        self.refresh()

    def _play_tick(self) -> None:
        if self.frame_i >= self._play_end:
            self._play_timer.stop()
            if not self.chk_replay.isChecked():
                self._space_should_advance = True
            return
        self.frame_i += 1
        if self.frame_i >= self._view_t1():
            self.view_t0 = int(np.clip(self.frame_i - self.view_len // 4, 0, max(self.n_frames - self.view_len, 0)))
        self.refresh()

    # ----- file / scorer -----

    def _pick_video(self) -> None:
        if self.video_path:
            start = str(self.video_path.parent)
        else:
            mp4 = _sibling_dir(None, _SIBLING_MP4)
            start = str(mp4 if mp4.is_dir() else Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Open OF video", start, "Video (*.mp4 *.avi *.mkv);;All (*.*)")
        if not path:
            return
        self.video_path = Path(path)
        self.video_id = self.video_path.stem
        guess = _guess_bouts_for_video(self.video_path)
        if guess is not None:
            self.bouts_path = guess
        if self.bouts_path is None:
            self._pick_bouts()
            return
        try:
            self._load_session()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(exc))

    def _pick_bouts(self) -> None:
        if self.bouts_path:
            start = str(self.bouts_path.parent)
        else:
            kpms = _sibling_dir(self.video_path, _SIBLING_KPMS)
            start = str(kpms if kpms.is_dir() else Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Open syllable_bouts.csv", start, "CSV (*.csv);;All (*.*)")
        if not path:
            return
        self.bouts_path = Path(path)
        try:
            self._load_session()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(exc))

    def _on_scorer_edit(self) -> None:
        self.scorer = sanitize_scorer(self.scorer_edit.text() or "scorer")
        self.scorer_edit.setText(self.scorer)
        self._release_scorer_focus()
        if self.bouts_path is None:
            return
        self.labels_path = default_labels_path(self.bouts_path, self.scorer)
        self.export_path = self.bouts_path.parent / "labels" / f"{self.scorer}_sturman_intervals.csv"
        self.labels = load_labels(self.labels_path, scorer=self.scorer)
        self.setWindowTitle(f"of_rear labeler — {self.video_id} [{self.scorer}]")
        self.refresh(labels_changed=True)

    # ----- events -----

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.video_label and event.type() == QEvent.Type.MouseButtonPress:
            self._release_scorer_focus()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        # Esc while editing scorer: cancel focus, don't clear manual range.
        if self._scorer_capturing():
            if event.key() == Qt.Key.Key_Escape:
                self._release_scorer_focus()
                return
            return super().keyPressEvent(event)

        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._play_timer.stop()
            self.manual_t0 = self.manual_t1 = None
            self.refresh(labels_changed=True)
            return
        if key == Qt.Key.Key_BracketLeft:
            self.manual_t0 = int(self.frame_i)
            self.refresh(labels_changed=True)
            return
        if key == Qt.Key.Key_BracketRight:
            self.manual_t1 = int(self.frame_i)
            if self.manual_t0 is None:
                self.manual_t0 = self.manual_t1
            self.refresh(labels_changed=True)
            return
        if key == Qt.Key.Key_C:
            self.manual_t0 = self.manual_t1 = None
            self.refresh(labels_changed=True)
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._play_timer.stop()
        if self.dirty:
            self.save()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._video_pix is not None and not self._video_pix.isNull():
            target = self.video_label.size()
            if target.width() >= 2 and target.height() >= 2:
                self.video_label.setPixmap(
                    self._video_pix.scaled(
                        target,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        self._update_timelines()


def run_app(
    *,
    video: Path | None = None,
    bouts: Path | None = None,
    scorer: str | None = None,
    fps: float | None = None,
    export_intervals: Path | None = None,
    video_id: str | None = None,
    mlp_pred: Path | None = None,
    auto_load_mlp: bool = True,
) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = SyllableLabelerWindow(
        video=video,
        bouts=bouts,
        scorer=scorer,
        fps=fps,
        export_intervals=export_intervals,
        video_id=video_id,
        mlp_pred=mlp_pred,
        auto_load_mlp=auto_load_mlp,
    )
    if not win.bootstrap():
        print("cancelled — need video + bouts + scorer", flush=True)
        return 1
    win.show()
    win._release_scorer_focus()
    print(
        f"loaded {len(win.bouts)} bouts · frames≈{win.n_frames} · fps={win.fps:.2f}\n"
        f"scorer={win.scorer} → {win.labels_path}\n"
        f"classes={LABEL_CLASSES}\n"
        f"timeline: overview+detail viewport (~{_DEFAULT_VIEW_SEC:.0f}s default; wheel pan, Ctrl+wheel zoom)",
        flush=True,
    )
    return app.exec()
