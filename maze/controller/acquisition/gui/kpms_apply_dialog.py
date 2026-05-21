"""Pipeline → kpMS apply dialog (Phase C5)."""

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
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    from maze.kpms.apply import DEFAULT_MANIFEST_CSV, run_kpms_apply
    from maze.kpms.apply_run_config import KpmsApplyRunConfig
    from maze.kpms.availability import is_kpms_available

    HAS_KPMS_APPLY_DIALOG = True
except ImportError:
    HAS_KPMS_APPLY_DIALOG = False

    def is_kpms_available() -> bool:
        return False

    QThread = object  # type: ignore[misc, assignment]


def _default_kpms_project_dir(config: "AcquisitionConfig") -> Path:
    out = (config.output_dir or "").strip()
    return Path(out) / "kpms" if out else Path("kpms")


def _default_manifest_csv_text(config: "AcquisitionConfig") -> str:
    out = (config.output_dir or "").strip()
    if out:
        candidate = Path(out) / "trial_manifest.csv"
        if candidate.is_file():
            return str(candidate)
    if DEFAULT_MANIFEST_CSV.is_file():
        return str(DEFAULT_MANIFEST_CSV)
    return ""


def _parse_optional_filter(text: str) -> Optional[tuple[str, ...]]:
    tokens = tuple(t.strip() for t in text.replace(",", " ").split() if t.strip())
    return tokens if tokens else None


if HAS_KPMS_APPLY_DIALOG:

    class KpmsApplyWorker(QThread):
        log_line = Signal(str)
        finished_ok = Signal(bool, str)

        def __init__(self, cfg: KpmsApplyRunConfig) -> None:
            super().__init__()
            self._cfg = cfg

        def run(self) -> None:
            buf = io.StringIO()
            try:
                with redirect_stdout(buf), redirect_stderr(buf):
                    summary = run_kpms_apply(self._cfg)
                self.log_line.emit(buf.getvalue())
                results = summary.get("results_path", "")
                self.finished_ok.emit(
                    True,
                    f"Apply finished. Results: {results}",
                )
            except Exception as e:
                self.log_line.emit(buf.getvalue())
                self.log_line.emit(traceback.format_exc())
                self.finished_ok.emit(False, f"{type(e).__name__}: {e}")

    def open_kpms_apply_dialog(parent: QWidget, config: "AcquisitionConfig") -> None:
        dlg = QDialog(parent)
        dlg.setWindowTitle("Pipeline — kpMS apply")
        lay = QVBoxLayout(dlg)
        out_hint = (config.output_dir or "").strip()

        hint = QLabel(
            "Apply a trained keypoint-MoSeq checkpoint to trials listed in a manifest CSV. "
            "Requires a prior fit (checkpoint under project directory / model name) and "
            "uv sync --extra kpms. Writes results_apply.h5 and apply_summary.json with provenance."
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)

        form = QFormLayout()
        manifest_edit = QLineEdit(_default_manifest_csv_text(config))
        project_edit = QLineEdit(str(_default_kpms_project_dir(config)))
        model_edit = QLineEdit("orm_kpms_fit")
        results_edit = QLineEdit()
        results_edit.setPlaceholderText("Default: <project>/<model>/results_apply.h5")
        animal_edit = QLineEdit()
        animal_edit.setPlaceholderText("Optional: comma-separated animal IDs")
        session_edit = QLineEdit()
        session_edit.setPlaceholderText("Optional: e.g. S01, S02")
        trial_edit = QLineEdit()
        trial_edit.setPlaceholderText("Optional: e.g. T01, T02")
        num_iters = QSpinBox()
        num_iters.setRange(1, 10_000)
        num_iters.setValue(100)

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
        form.addRow("Project directory:", proj_row)
        form.addRow("Model name:", model_edit)
        form.addRow("Results HDF5 (optional):", results_edit)
        form.addRow("Animal ID filter:", animal_edit)
        form.addRow("Session filter:", session_edit)
        form.addRow("Trial filter:", trial_edit)
        form.addRow("num_iters:", num_iters)
        lay.addLayout(form)

        incl_hab = QCheckBox("Include habituation trials")
        excl_exp = QCheckBox("Exclude experimental trials")
        enrich_cb = QCheckBox("Enrich blank sex/tx from treatment_labels.csv")
        enrich_cb.setChecked(True)
        reindex_cb = QCheckBox("Reindex syllables before load")
        reindex_cb.setChecked(True)
        overwrite_cb = QCheckBox("Overwrite existing results keys")
        overwrite_cb.setChecked(True)
        lay.addWidget(incl_hab)
        lay.addWidget(excl_exp)
        lay.addWidget(enrich_cb)
        lay.addWidget(reindex_cb)
        lay.addWidget(overwrite_cb)

        log = QPlainTextEdit()
        log.setReadOnly(True)
        log.setMinimumHeight(200)
        lay.addWidget(log)

        worker: Optional[KpmsApplyWorker] = None

        def on_done(ok: bool, msg: str) -> None:
            nonlocal worker
            worker = None
            log.appendPlainText(msg + "\n")
            (QMessageBox.information if ok else QMessageBox.warning)(dlg, "kpMS apply", msg)

        def run_apply() -> None:
            nonlocal worker
            if not is_kpms_available():
                QMessageBox.warning(
                    dlg,
                    "kpMS apply",
                    "keypoint-moseq is not installed. Run: uv sync --extra kpms",
                )
                return
            mpath = Path(manifest_edit.text().strip())
            if not mpath.is_file():
                QMessageBox.warning(dlg, "kpMS apply", f"Manifest CSV not found: {mpath}")
                return
            pdir = Path(project_edit.text().strip())
            if not pdir:
                QMessageBox.warning(dlg, "kpMS apply", "Project directory is required.")
                return
            model = model_edit.text().strip()
            if not model:
                QMessageBox.warning(dlg, "kpMS apply", "Model name is required.")
                return
            rtext = results_edit.text().strip()
            results_path = Path(rtext) if rtext else None
            if worker is not None:
                return
            cfg = KpmsApplyRunConfig(
                project_dir=pdir,
                model_name=model,
                manifest_csv=mpath,
                results_path=results_path,
                animal_ids=_parse_optional_filter(animal_edit.text()),
                sessions=_parse_optional_filter(session_edit.text()),
                trials=_parse_optional_filter(trial_edit.text()),
                include_habituation=incl_hab.isChecked(),
                exclude_experimental=excl_exp.isChecked(),
                enrich_from_treatment_labels=enrich_cb.isChecked(),
                num_iters=int(num_iters.value()),
                reindex_syllables_before_load=reindex_cb.isChecked(),
                overwrite_results=overwrite_cb.isChecked(),
                verbose=True,
            )
            worker = KpmsApplyWorker(cfg)
            worker.log_line.connect(log.appendPlainText)
            worker.finished_ok.connect(on_done)
            worker.start()

        lay.addWidget(QPushButton("Run kpMS apply", clicked=run_apply))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(640, 560)
        dlg.show()

else:

    def open_kpms_apply_dialog(parent: object, config: object) -> None:
        del parent, config
