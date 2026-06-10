"""Pipeline → kpMS fit dialog (Phase C4)."""

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
        QComboBox,
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
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    from maze.kpms.apply import DEFAULT_MANIFEST_CSV
    from maze.kpms.availability import is_kpms_available
    from maze.kpms.fit import run_kpms_fit
    from maze.kpms.fit_config import KpmsFitRunConfig
    from maze.kpms.project_paths import POSE_STREAM_CHOICES, default_kpms_root

    HAS_KPMS_FIT_DIALOG = True
except ImportError:
    HAS_KPMS_FIT_DIALOG = False

    def is_kpms_available() -> bool:
        return False

    QThread = object  # type: ignore[misc, assignment]


def _default_kpms_root_dir(config: "AcquisitionConfig") -> Path:
    out = (config.output_dir or "").strip()
    return default_kpms_root(out) if out else default_kpms_root(".")


def _default_manifest_csv_text(config: "AcquisitionConfig") -> str:
    out = (config.output_dir or "").strip()
    if out:
        candidate = Path(out) / "trial_manifest.csv"
        if candidate.is_file():
            return str(candidate)
    if DEFAULT_MANIFEST_CSV.is_file():
        return str(DEFAULT_MANIFEST_CSV)
    return ""


if HAS_KPMS_FIT_DIALOG:

    class KpmsFitWorker(QThread):
        log_line = Signal(str)
        finished_ok = Signal(bool, str)

        def __init__(self, cfg: KpmsFitRunConfig) -> None:
            super().__init__()
            self._cfg = cfg

        def run(self) -> None:
            buf = io.StringIO()
            try:
                with redirect_stdout(buf), redirect_stderr(buf):
                    out_dir = run_kpms_fit(self._cfg)
                self.log_line.emit(buf.getvalue())
                self.finished_ok.emit(True, f"Fit finished. Model directory: {out_dir}")
            except Exception as e:
                self.log_line.emit(buf.getvalue())
                self.log_line.emit(traceback.format_exc())
                self.finished_ok.emit(False, f"{type(e).__name__}: {e}")

    def open_kpms_fit_dialog(parent: QWidget, config: "AcquisitionConfig") -> None:
        dlg = QDialog(parent)
        dlg.setWindowTitle("Pipeline — kpMS fit")
        lay = QVBoxLayout(dlg)
        out_hint = (config.output_dir or "").strip()

        hint = QLabel(
            "Slow job (minutes–hours): fits a keypoint-MoSeq model from a trial manifest CSV. "
            "Pose stream selects anatomical (SLEAP/H5), blob (backup tracker), or fused (both). "
            "Outputs go to <project-dir>/<stream>/<model-name>/ (e.g. kpms/anatomical/orm_kpms_fit). "
            "Requires uv sync --extra kpms. Use Force new when reusing a model name after subset changes."
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)

        form = QFormLayout()
        manifest_edit = QLineEdit(_default_manifest_csv_text(config))
        project_edit = QLineEdit(str(_default_kpms_root_dir(config)))
        stream_combo = QComboBox()
        for stream in POSE_STREAM_CHOICES:
            stream_combo.addItem(stream, stream)
        model_edit = QLineEdit("orm_kpms_fit")
        max_trials = QSpinBox()
        max_trials.setRange(1, 10_000)
        max_trials.setValue(300)
        seed_spin = QSpinBox()
        seed_spin.setRange(0, 2_147_483_647)
        seed_spin.setValue(42)
        balance_edit = QLineEdit("sex,tx,phase,strain")

        def browse_manifest() -> None:
            start = str(Path(manifest_edit.text()).parent)
            if not start or start == ".":
                start = out_hint or str(DEFAULT_MANIFEST_CSV.parent)
            p, _ = QFileDialog.getOpenFileName(dlg, "Trial manifest CSV", start, "CSV (*.csv)")
            if p:
                manifest_edit.setText(p)

        def browse_project() -> None:
            d = QFileDialog.getExistingDirectory(
                dlg,
                "kpMS project directory",
                project_edit.text().strip() or out_hint or "",
            )
            if d:
                project_edit.setText(d)

        man_row = QWidget()
        man_h = QHBoxLayout(man_row)
        man_h.setContentsMargins(0, 0, 0, 0)
        man_h.addWidget(manifest_edit)
        man_h.addWidget(QPushButton("Browse…", clicked=browse_manifest))
        form.addRow("Manifest CSV:", man_row)

        proj_row = QWidget()
        proj_h = QHBoxLayout(proj_row)
        proj_h.setContentsMargins(0, 0, 0, 0)
        proj_h.addWidget(project_edit)
        proj_h.addWidget(QPushButton("Browse…", clicked=browse_project))
        form.addRow("Project directory (kpMS root):", proj_row)
        form.addRow("Pose stream:", stream_combo)
        form.addRow("Model name:", model_edit)
        form.addRow("Max trials:", max_trials)
        form.addRow("Random seed:", seed_spin)
        form.addRow("Balance by (comma):", balance_edit)

        lay.addLayout(form)
        incl_hab = QCheckBox("Include habituation trials")
        excl_exp = QCheckBox("Exclude experimental trials")
        enrich_cb = QCheckBox("Enrich blank sex/tx from treatment_labels.csv")
        enrich_cb.setChecked(True)
        force_cb = QCheckBox("Force new checkpoint (--force-new)")
        force_cb.setToolTip("Delete existing checkpoint.h5 for this model name before fitting.")
        lay.addWidget(incl_hab)
        lay.addWidget(excl_exp)
        lay.addWidget(enrich_cb)
        lay.addWidget(force_cb)

        log = QPlainTextEdit()
        log.setReadOnly(True)
        log.setMinimumHeight(200)
        lay.addWidget(log)

        worker: Optional[KpmsFitWorker] = None

        def on_done(ok: bool, msg: str) -> None:
            nonlocal worker
            worker = None
            log.appendPlainText(msg + "\n")
            (QMessageBox.information if ok else QMessageBox.warning)(dlg, "kpMS fit", msg)

        def run_fit() -> None:
            nonlocal worker
            if not is_kpms_available():
                QMessageBox.warning(
                    dlg,
                    "kpMS fit",
                    "keypoint-moseq is not installed. Run: uv sync --extra kpms",
                )
                return
            mpath = Path(manifest_edit.text().strip())
            if not mpath.is_file():
                QMessageBox.warning(dlg, "kpMS fit", f"Manifest CSV not found: {mpath}")
                return
            pdir = Path(project_edit.text().strip())
            if not pdir:
                QMessageBox.warning(dlg, "kpMS fit", "Project directory is required.")
                return
            balance_cols = tuple(
                c.strip() for c in balance_edit.text().split(",") if c.strip()
            )
            if worker is not None:
                return
            pose_stream = stream_combo.currentData()
            if not isinstance(pose_stream, str):
                pose_stream = "anatomical"
            cfg = KpmsFitRunConfig(
                project_dir=pdir,
                model_name=model_edit.text().strip() or "orm_kpms_fit",
                pose_stream=pose_stream,  # type: ignore[arg-type]
                manifest_csv=mpath,
                max_trials=int(max_trials.value()),
                random_seed=int(seed_spin.value()),
                include_habituation=incl_hab.isChecked(),
                exclude_experimental=excl_exp.isChecked(),
                balance_columns=balance_cols or ("sex", "tx", "phase", "strain"),
                enrich_from_treatment_labels=enrich_cb.isChecked(),
                force_new=force_cb.isChecked(),
            )
            worker = KpmsFitWorker(cfg)
            worker.log_line.connect(log.appendPlainText)
            worker.finished_ok.connect(on_done)
            worker.start()

        lay.addWidget(QPushButton("Run kpMS fit", clicked=run_fit))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(620, 520)
        dlg.show()

else:

    def open_kpms_fit_dialog(parent: object, config: object) -> None:
        del parent, config
