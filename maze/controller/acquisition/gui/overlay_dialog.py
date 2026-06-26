"""Pipeline → Render unified overlay dialog (Phase C9)."""

from __future__ import annotations

import io
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..shared_config import AcquisitionConfig

try:
    from PySide6.QtCore import QThread, Signal
    from PySide6.QtWidgets import (
        QCheckBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    from maze.kpms.apply import DEFAULT_MANIFEST_CSV
    from maze.kpms.availability import is_kpms_available
    from maze.pipeline.viz.overlay_cli import is_unified_overlay_available, run_unified_overlay
    from maze.pipeline.viz.overlay_run_config import UnifiedOverlayRunConfig

    HAS_OVERLAY_DIALOG = True
except ImportError:
    HAS_OVERLAY_DIALOG = False

    def is_unified_overlay_available() -> bool:
        return False

    def is_kpms_available() -> bool:
        return False

    QThread = object  # type: ignore[misc, assignment]


def _default_manifest_csv_text(config: "AcquisitionConfig") -> str:
    out = (config.output_dir or "").strip()
    if out:
        candidate = Path(out) / "trial_manifest.csv"
        if candidate.is_file():
            return str(candidate)
    if DEFAULT_MANIFEST_CSV.is_file():
        return str(DEFAULT_MANIFEST_CSV)
    return ""


def _default_pipeline_h5(config: "AcquisitionConfig") -> Path:
    out = (config.output_dir or "").strip()
    name = (config.h5_filename or "trials.h5").strip() or "trials.h5"
    if Path(name).name != name:
        name = Path(name).name
    return Path(out) / name if out else Path(name)


def _default_overlay_out_dir(config: "AcquisitionConfig") -> Path:
    out = (config.output_dir or "").strip()
    return Path(out) / "overlays" if out else Path("overlays")


if HAS_OVERLAY_DIALOG:

    class OverlayRenderWorker(QThread):
        log_line = Signal(str)
        finished_ok = Signal(bool, str)

        def __init__(self, cfg: UnifiedOverlayRunConfig) -> None:
            super().__init__()
            self._cfg = cfg

        def run(self) -> None:
            buf = io.StringIO()
            try:
                with redirect_stdout(buf), redirect_stderr(buf):
                    out = run_unified_overlay(self._cfg)
                self.log_line.emit(buf.getvalue())
                self.finished_ok.emit(True, f"Overlay written: {out}")
            except Exception as e:
                self.log_line.emit(buf.getvalue())
                self.log_line.emit(traceback.format_exc())
                self.finished_ok.emit(False, f"{type(e).__name__}: {e}")

    def open_overlay_dialog(parent: QWidget, config: "AcquisitionConfig") -> None:
        dlg = QDialog(parent)
        dlg.setWindowTitle("Pipeline — Render unified overlay")
        lay = QVBoxLayout(dlg)
        out_hint = (config.output_dir or "").strip()

        hint = QLabel(
            "Render one trial MP4: source video + pipeline HDF5 + optional kpMS ethogram/tray. "
            "Requires OpenCV (opencv-python). kpMS layers need uv sync --extra kpms. "
            "CLI equivalent: uv run maze-render-trial-overlay --help"
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)

        form = QFormLayout()
        manifest_edit = QLineEdit(_default_manifest_csv_text(config))
        pipeline_edit = QLineEdit(str(_default_pipeline_h5(config)))
        animal_edit = QLineEdit()
        session_edit = QLineEdit("S01")
        trial_edit = QLineEdit("T01")
        out_edit = QLineEdit(str(_default_overlay_out_dir(config)))
        kpms_edit = QLineEdit()
        kpms_edit.setPlaceholderText("Optional results_apply.h5 for ethogram")

        def browse_manifest() -> None:
            start = str(Path(manifest_edit.text()).parent)
            if not start or start == ".":
                start = out_hint or str(DEFAULT_MANIFEST_CSV.parent)
            p, _ = QFileDialog.getOpenFileName(dlg, "Trial manifest CSV", start, "CSV (*.csv)")
            if p:
                manifest_edit.setText(p)

        def browse_pipeline() -> None:
            p, _ = QFileDialog.getOpenFileName(
                dlg,
                "Pipeline HDF5",
                pipeline_edit.text().strip() or out_hint,
                "HDF5 (*.h5 *.hdf5);;All (*)",
            )
            if p:
                pipeline_edit.setText(p)

        def browse_out() -> None:
            d = QFileDialog.getExistingDirectory(
                dlg,
                "Output directory",
                out_edit.text().strip() or out_hint or "",
            )
            if d:
                out_edit.setText(d)

        def browse_kpms() -> None:
            p, _ = QFileDialog.getOpenFileName(
                dlg,
                "kpMS results HDF5",
                kpms_edit.text().strip() or out_hint,
                "HDF5 (*.h5 *.hdf5);;All (*)",
            )
            if p:
                kpms_edit.setText(p)

        man_row = QWidget()
        man_h = QHBoxLayout(man_row)
        man_h.setContentsMargins(0, 0, 0, 0)
        man_h.addWidget(manifest_edit)
        man_h.addWidget(QPushButton("Browse…", clicked=browse_manifest))
        form.addRow("Manifest CSV:", man_row)

        pipe_row = QWidget()
        pipe_h = QHBoxLayout(pipe_row)
        pipe_h.setContentsMargins(0, 0, 0, 0)
        pipe_h.addWidget(pipeline_edit)
        pipe_h.addWidget(QPushButton("Browse…", clicked=browse_pipeline))
        form.addRow("Pipeline H5:", pipe_row)
        form.addRow("Animal ID:", animal_edit)
        form.addRow("Session:", session_edit)
        form.addRow("Trial:", trial_edit)

        out_row = QWidget()
        out_h = QHBoxLayout(out_row)
        out_h.setContentsMargins(0, 0, 0, 0)
        out_h.addWidget(out_edit)
        out_h.addWidget(QPushButton("Browse…", clicked=browse_out))
        form.addRow("Output dir:", out_row)

        kpms_row = QWidget()
        kpms_h = QHBoxLayout(kpms_row)
        kpms_h.setContentsMargins(0, 0, 0, 0)
        kpms_h.addWidget(kpms_edit)
        kpms_h.addWidget(QPushButton("Browse…", clicked=browse_kpms))
        form.addRow("kpMS H5 (optional):", kpms_row)
        lay.addLayout(form)

        no_hyp = QCheckBox("Disable ethogram strip")
        no_tray = QCheckBox("Disable syllable exemplar tray")
        no_skel = QCheckBox("Hide SLEAP skeleton")
        lay.addWidget(no_hyp)
        lay.addWidget(no_tray)
        lay.addWidget(no_skel)

        log = QPlainTextEdit()
        log.setReadOnly(True)
        log.setMinimumHeight(160)
        lay.addWidget(log)

        worker: Optional[OverlayRenderWorker] = None

        def on_done(ok: bool, msg: str) -> None:
            nonlocal worker
            worker = None
            log.appendPlainText(msg + "\n")
            (QMessageBox.information if ok else QMessageBox.warning)(dlg, "Unified overlay", msg)

        def run_render() -> None:
            nonlocal worker
            if not is_unified_overlay_available():
                QMessageBox.warning(
                    dlg,
                    "Unified overlay",
                    "OpenCV is not installed. Install opencv-python (see pyproject gui extra).",
                )
                return
            mpath = Path(manifest_edit.text().strip())
            if not mpath.is_file():
                QMessageBox.warning(dlg, "Unified overlay", f"Manifest CSV not found: {mpath}")
                return
            ph5 = Path(pipeline_edit.text().strip())
            if not ph5.is_file():
                QMessageBox.warning(dlg, "Unified overlay", f"Pipeline H5 not found: {ph5}")
                return
            aid = animal_edit.text().strip()
            sess = session_edit.text().strip()
            tri = trial_edit.text().strip()
            if not aid or not sess or not tri:
                QMessageBox.warning(dlg, "Unified overlay", "Animal ID, session, and trial are required.")
                return
            out_dir = Path(out_edit.text().strip())
            if not out_dir:
                QMessageBox.warning(dlg, "Unified overlay", "Output directory is required.")
                return
            kpath = kpms_edit.text().strip()
            if kpath and not is_kpms_available():
                QMessageBox.warning(
                    dlg,
                    "Unified overlay",
                    "kpMS H5 set but keypoint-moseq is not installed. "
                    "Run: uv sync --extra kpms — or clear kpMS H5 to render without ethogram.",
                )
                return
            if worker is not None:
                return
            cfg = UnifiedOverlayRunConfig(
                manifest_csv=mpath,
                pipeline_h5=ph5,
                animal_id=aid,
                session=sess,
                trial=tri,
                out=out_dir,
                kpms_h5=Path(kpath) if kpath else None,
                no_ethogram=no_hyp.isChecked(),
                no_syllable_tray=no_tray.isChecked(),
                no_skeleton=no_skel.isChecked(),
            )
            worker = OverlayRenderWorker(cfg)
            worker.log_line.connect(log.appendPlainText)
            worker.finished_ok.connect(on_done)
            worker.start()

        lay.addWidget(QPushButton("Render overlay", clicked=run_render))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(620, 520)
        dlg.show()

else:

    def open_overlay_dialog(parent: object, config: object) -> None:
        del parent, config
