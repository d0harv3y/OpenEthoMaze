"""Pipeline menu: Discovery, virtual acquisition, and Analyze dialogs (batch helpers)."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

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

    HAS_QT = True
except ImportError:
    HAS_QT = False
    QThread = object  # type: ignore[misc, assignment]


def _default_h5_path(config: "AcquisitionConfig") -> Path:
    out = config.output_dir or ""
    name = (config.h5_filename or "trials.h5").strip() or "trials.h5"
    if Path(name).name != name:
        name = Path(name).name
    return Path(out) / name if out else Path(name)


def _parse_filter_list(raw: str) -> Optional[list[str]]:
    s = (raw or "").strip()
    if not s:
        return None
    return [x.strip() for x in s.replace(",", " ").split() if x.strip()]


def _parse_data_dirs_text(raw: str) -> Optional[list[Path]]:
    """Split user-entered roots (newline or ``;``). Empty / whitespace-only → ``None`` (use defaults)."""
    paths: list[Path] = []
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    for line in text.split("\n"):
        for segment in line.split(";"):
            p = segment.strip().strip('"')
            if p:
                paths.append(Path(p))
    return paths or None


if HAS_QT:

    def _inference_planned_slp(video_path: Path, output_dir: Optional[Path]) -> Path:
        name = video_path.with_suffix(".predictions.slp").name
        return (output_dir / name) if output_dir else video_path.with_suffix(".predictions.slp")

    def _find_existing_pose_file(
        *,
        video_path: Path,
        manifest_sleap: Optional[Path],
        planned_out: Path,
    ) -> Optional[Path]:
        """Return first existing pose file among DB path, planned output, and video-sidecar names."""
        candidates: list[Optional[Path]] = [
            manifest_sleap,
            planned_out,
            video_path.with_suffix(".predictions.slp"),
            video_path.with_suffix(".slp"),
        ]
        seen: set[str] = set()
        for p in candidates:
            if p is None:
                continue
            try:
                key = str(p.resolve())
            except OSError:
                continue
            if key in seen:
                continue
            seen.add(key)
            if p.exists():
                return p
        return None

    class _InferenceWorker(QThread):
        log_line = Signal(str)
        finished_ok = Signal(bool, str)

        def __init__(
            self,
            *,
            db_path: Path,
            model_path: Path,
            config: "AcquisitionConfig",
            device: str,
            batch_size: int,
            skip_existing: bool,
            materialize_xy: bool,
            output_dir: Optional[Path],
            animal_ids: Optional[list[str]],
            sessions: Optional[list[str]],
            trials: Optional[list[str]],
        ) -> None:
            super().__init__()
            self._db_path = db_path
            self._model_path = model_path
            self._config = config
            self._device = device
            self._batch_size = batch_size
            self._skip_existing = skip_existing
            self._materialize_xy = materialize_xy
            self._output_dir = output_dir
            self._animal_ids = animal_ids
            self._sessions = sessions
            self._trials = trials

        def run(self) -> None:
            from maze.pipeline.db import TrialKey, write_sleap_model_path, write_sleap_path
            from maze.pipeline.headless_encode import materialize_xy_tables_from_video
            from maze.pipeline.inference_backend import get_backend
            from maze.pipeline.run_pipeline import load_trial_manifests_from_db

            try:
                backend = get_backend("sleap_nn")
                manifests = load_trial_manifests_from_db(self._db_path)
                if self._animal_ids:
                    manifests = [m for m in manifests if m.animal_id in self._animal_ids]
                if self._sessions:
                    manifests = [m for m in manifests if m.session in self._sessions]
                if self._trials:
                    manifests = [m for m in manifests if m.trial in self._trials]
                with_video = [m for m in manifests if m.video_path and m.video_path.exists()]
                if not with_video:
                    self.finished_ok.emit(False, "No trials with video.")
                    return
                n_ok = 0
                for i, m in enumerate(with_video, 1):
                    vp = m.video_path
                    assert vp is not None
                    out_path = _inference_planned_slp(vp, self._output_dir)
                    existing = _find_existing_pose_file(
                        video_path=vp,
                        manifest_sleap=m.sleap_path,
                        planned_out=out_path,
                    )
                    if self._skip_existing and existing is not None:
                        self.log_line.emit(
                            f"[{i}/{len(with_video)}] skip existing pose {m.trial_key} → {existing}"
                        )
                        key = TrialKey.from_manifest(m)
                        write_sleap_path(self._db_path, key, str(existing.resolve()))
                        write_sleap_model_path(self._db_path, key, str(self._model_path.resolve()))
                        if self._materialize_xy and vp.exists():
                            materialize_xy_tables_from_video(
                                db_path=self._db_path,
                                key=key,
                                video_path=vp,
                                config=self._config,
                                model_dir=str(self._model_path),
                            )
                        n_ok += 1
                        continue
                    self.log_line.emit(f"[{i}/{len(with_video)}] {m.trial_key} -> {out_path}")
                    pred = backend.run(
                        video_path=vp,
                        model_path=self._model_path,
                        output_path=out_path,
                        device=self._device,
                        batch_size=self._batch_size,
                    )
                    if pred is None or not pred.exists():
                        self.log_line.emit(f"  FAILED inference for {m.trial_key}")
                        continue
                    key = TrialKey.from_manifest(m)
                    write_sleap_path(self._db_path, key, str(pred.resolve()))
                    write_sleap_model_path(self._db_path, key, str(self._model_path.resolve()))
                    if self._materialize_xy:
                        materialize_xy_tables_from_video(
                            db_path=self._db_path,
                            key=key,
                            video_path=vp,
                            config=self._config,
                            model_dir=str(self._model_path),
                        )
                    n_ok += 1
                self.finished_ok.emit(
                    True,
                    f"Virtual acquisition finished ({n_ok}/{len(with_video)} trials processed).",
                )
            except Exception as e:
                self.log_line.emit(traceback.format_exc())
                self.finished_ok.emit(False, f"{type(e).__name__}: {e}")

    class _AnalyzeWorker(QThread):
        log_line = Signal(str)
        finished_ok = Signal(bool, str)

        def __init__(
            self,
            *,
            db_path: Path,
            generate_qc: bool,
            skip_mistrials: bool,
            max_workers: int,
            animal_ids: Optional[list[str]],
            sessions: Optional[list[str]],
            trials: Optional[list[str]],
            analysis_profile: Optional[tuple] = None,
        ) -> None:
            super().__init__()
            self._db_path = db_path
            self._generate_qc = generate_qc
            self._skip_mistrials = skip_mistrials
            self._max_workers = max_workers
            self._animal_ids = animal_ids
            self._sessions = sessions
            self._trials = trials
            self._analysis_profile = analysis_profile

        def run(self) -> None:
            import io
            from contextlib import redirect_stderr, redirect_stdout

            from maze.pipeline.run_pipeline import run_pipeline

            buf = io.StringIO()
            try:
                with redirect_stdout(buf), redirect_stderr(buf):
                    stats = run_pipeline(
                        db_path=self._db_path,
                        animal_ids=self._animal_ids,
                        sessions=self._sessions,
                        trial_names=self._trials,
                        generate_qc=self._generate_qc,
                        skip_mistrials=self._skip_mistrials,
                        max_workers=self._max_workers,
                        parallel=False,
                        analysis_profile=self._analysis_profile,
                        prefilter_mode="controller",
                    )
                self.log_line.emit(buf.getvalue())
                failed = int(stats.get("failed", 0) or 0)
                self.finished_ok.emit(
                    failed == 0,
                    f"Done: {stats.get('success', 0)} ok, {failed} failed.",
                )
            except Exception as e:
                self.log_line.emit(buf.getvalue())
                self.log_line.emit(traceback.format_exc())
                self.finished_ok.emit(False, f"{type(e).__name__}: {e}")

    def open_discovery_dialog(parent: QWidget, config: "AcquisitionConfig") -> None:
        dlg = QDialog(parent)
        dlg.setWindowTitle("Pipeline — Discovery")
        v = QVBoxLayout(dlg)
        form = QFormLayout()
        h5_edit = QLineEdit(str(_default_h5_path(config)))
        lbl_edit = QLineEdit()
        from maze.pipeline.io.file_discovery import TREATMENT_LABELS_HEADER
        from maze.pipeline.paths import DATA_DIRS

        _orm_root = Path(__file__).resolve().parents[4]
        default_lbl = _orm_root / "inputs" / "treatment_labels.csv"
        lbl_edit.setText(str(default_lbl))
        dirs_edit = QLineEdit("; ".join(str(p) for p in DATA_DIRS))
        dirs_edit.setPlaceholderText(
            "One path per line, or separate with ; (empty = use paths.py defaults)"
        )

        def browse_h5() -> None:
            p, _ = QFileDialog.getOpenFileName(
                dlg, "Results H5", str(Path(h5_edit.text()).parent), "H5 (*.h5)"
            )
            if p:
                h5_edit.setText(p)

        def browse_lbl() -> None:
            p, _ = QFileDialog.getOpenFileName(dlg, "Treatment labels", "", "CSV (*.csv)")
            if p:
                lbl_edit.setText(p)

        def browse_data_dir() -> None:
            d = QFileDialog.getExistingDirectory(dlg, "Add data root for discovery scan", "")
            if not d:
                return
            cur = dirs_edit.text().strip()
            dirs_edit.setText(f"{cur}; {d}" if cur else d)

        h5_row = QWidget()
        h5_h = QHBoxLayout(h5_row)
        h5_h.setContentsMargins(0, 0, 0, 0)
        h5_h.addWidget(h5_edit)
        h5_h.addWidget(QPushButton("Browse…", clicked=browse_h5))
        form.addRow("Target H5:", h5_row)

        lbl_row = QWidget()
        lbl_h = QHBoxLayout(lbl_row)
        lbl_h.setContentsMargins(0, 0, 0, 0)
        lbl_h.addWidget(lbl_edit)
        lbl_h.addWidget(QPushButton("Browse…", clicked=browse_lbl))
        create_lbl_btn = QPushButton("Create new…")
        create_lbl_btn.setEnabled(False)
        create_lbl_btn.setToolTip("Treatment table editor (placeholder).")
        lbl_h.addWidget(create_lbl_btn)
        form.addRow("Treatment labels CSV:", lbl_row)

        dirs_row = QWidget()
        dirs_h = QHBoxLayout(dirs_row)
        dirs_h.setContentsMargins(0, 0, 0, 0)
        dirs_h.addWidget(dirs_edit)
        dirs_h.addWidget(QPushButton("Browse…", clicked=browse_data_dir))
        form.addRow("Data directories:", dirs_row)

        v.addLayout(form)
        log = QPlainTextEdit()
        log.setReadOnly(True)
        log.setMinimumHeight(180)
        v.addWidget(log)
        merge_cb = QCheckBox("Merge new animal IDs into treatment CSV (like sync --update-labels)")
        v.addWidget(merge_cb)

        def do_discover() -> None:
            from maze.pipeline.sources.legacy_vast import check_duplicates, discover_trials

            try:
                dd = _parse_data_dirs_text(dirs_edit.text())
                r = discover_trials(dd)
                dups = check_duplicates(r)
                log.appendPlainText(
                    f"Trials: {len(r.trials)}, videos matched: {r.n_matched_videos}, "
                    f"sleap matched: {r.n_matched_sleap}\n"
                )
                if dups:
                    log.appendPlainText(f"Duplicates: {len(dups)} keys (showing 5)\n")
                    for key, trials in dups[:5]:
                        log.appendPlainText(f"  {key}: {len(trials)} sources\n")
                else:
                    log.appendPlainText("No duplicate trial keys.\n")
                log.appendPlainText(f"CSV header: {TREATMENT_LABELS_HEADER}\n")
            except Exception as e:
                log.appendPlainText(traceback.format_exc())
                QMessageBox.warning(dlg, "Discovery", str(e))

        def do_sync() -> None:
            from maze.pipeline.discovery_sync import sync_discovery_into_h5

            try:
                dbp = Path(h5_edit.text().strip())
                lp = Path(lbl_edit.text().strip()) if lbl_edit.text().strip() else None
                dd = _parse_data_dirs_text(dirs_edit.text())
                _, dups = sync_discovery_into_h5(
                    dbp,
                    treatment_labels_path=lp,
                    merge_new_label_ids=merge_cb.isChecked(),
                    data_dirs=dd,
                )
                log.appendPlainText(f"Synced → {dbp}\n")
                if dups:
                    log.appendPlainText(f"Note: {len(dups)} duplicate keys in discovery.\n")
                QMessageBox.information(dlg, "Discovery", "Sync completed.")
            except Exception as e:
                log.appendPlainText(traceback.format_exc())
                QMessageBox.warning(dlg, "Discovery", str(e))

        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("Discover (scan only)", clicked=do_discover))
        btn_row.addWidget(QPushButton("Sync to H5", clicked=do_sync))
        v.addLayout(btn_row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        dlg.resize(640, 520)
        dlg.show()

    def open_inference_dialog(parent: QWidget, config: "AcquisitionConfig") -> None:
        dlg = QDialog(parent)
        dlg.setWindowTitle("Pipeline — Virtual acquisition")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        h5_edit = QLineEdit(str(_default_h5_path(config)))
        model_edit = QLineEdit((config.sleap_model_path or "").strip())
        out_edit = QLineEdit("")
        dev_edit = QLineEdit("auto")
        batch = QSpinBox()
        batch.setRange(1, 128)
        batch.setValue(4)
        skip_cb = QCheckBox(
            "Skip if pose output already exists (DB path, planned output, or video .slp / .predictions.slp)"
        )
        skip_cb.setChecked(True)
        mat_cb = QCheckBox("Materialize spot / in-range / centroid tables (headless encode)")
        mat_cb.setChecked(True)
        fa = QLineEdit("")
        fs = QLineEdit("")
        ft = QLineEdit("")

        def browse_h5() -> None:
            p, _ = QFileDialog.getOpenFileName(dlg, "H5", "", "H5 (*.h5)")
            if p:
                h5_edit.setText(p)

        def browse_model() -> None:
            p = QFileDialog.getExistingDirectory(dlg, "SLEAP model directory")
            if p:
                model_edit.setText(p)

        h5_row = QWidget()
        h5_h = QHBoxLayout(h5_row)
        h5_h.setContentsMargins(0, 0, 0, 0)
        h5_h.addWidget(h5_edit)
        h5_h.addWidget(QPushButton("Browse…", clicked=browse_h5))
        form.addRow("Target H5:", h5_row)

        model_row = QWidget()
        model_h = QHBoxLayout(model_row)
        model_h.setContentsMargins(0, 0, 0, 0)
        model_h.addWidget(model_edit)
        model_h.addWidget(QPushButton("Browse…", clicked=browse_model))
        form.addRow("Model directory (best.ckpt):", model_row)
        form.addRow("Prediction output dir (optional):", out_edit)
        form.addRow("Device:", dev_edit)
        form.addRow("Batch size:", batch)
        lay.addLayout(form)
        lay.addWidget(skip_cb)
        lay.addWidget(mat_cb)
        flt = QFormLayout()
        flt.addRow("Filter animal IDs:", fa)
        flt.addRow("Filter sessions:", fs)
        flt.addRow("Filter trials:", ft)
        lay.addLayout(flt)
        log = QPlainTextEdit()
        log.setReadOnly(True)
        lay.addWidget(log)

        worker: Optional[_InferenceWorker] = None

        def on_done(ok: bool, msg: str) -> None:
            nonlocal worker
            worker = None
            log.appendPlainText(msg + "\n")
            (
                QMessageBox.information(dlg, "Virtual acquisition", msg)
                if ok
                else QMessageBox.warning(dlg, "Virtual acquisition", msg)
            )

        def run_inf() -> None:
            nonlocal worker
            mp = Path(model_edit.text().strip())
            if not mp.is_dir() or not (mp / "best.ckpt").exists():
                QMessageBox.warning(
                    dlg,
                    "Virtual acquisition",
                    "Model path must be a directory containing best.ckpt.",
                )
                return
            if worker is not None:
                return
            odir = out_edit.text().strip()
            worker = _InferenceWorker(
                db_path=Path(h5_edit.text().strip()),
                model_path=mp,
                config=config,
                device=dev_edit.text().strip() or "auto",
                batch_size=int(batch.value()),
                skip_existing=skip_cb.isChecked(),
                materialize_xy=mat_cb.isChecked(),
                output_dir=Path(odir) if odir else None,
                animal_ids=_parse_filter_list(fa.text()),
                sessions=_parse_filter_list(fs.text()),
                trials=_parse_filter_list(ft.text()),
            )
            worker.log_line.connect(log.appendPlainText)
            worker.finished_ok.connect(on_done)
            worker.start()

        lay.addWidget(QPushButton("Run virtual acquisition", clicked=run_inf))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(560, 480)
        dlg.show()

    def open_analyze_dialog(parent: QWidget, config: "AcquisitionConfig") -> None:
        dlg = QDialog(parent)
        dlg.setWindowTitle("Pipeline — Analyze")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        h5_edit = QLineEdit(str(_default_h5_path(config)))
        workers = QSpinBox()
        workers.setRange(1, 32)
        workers.setValue(1)
        qc_cb = QCheckBox("Generate QC images")
        qc_cb.setChecked(True)
        skip_cb = QCheckBox("Skip mistrials (write mistrial_reason for bad inputs)")
        skip_cb.setChecked(True)
        prof_cb = QCheckBox("Apply current analysis profile (trajectory + trace quality)")
        prof_cb.setChecked(False)
        fa = QLineEdit("")
        fs = QLineEdit("")
        ft = QLineEdit("")

        def browse_h5() -> None:
            p, _ = QFileDialog.getOpenFileName(dlg, "H5", "", "H5 (*.h5)")
            if p:
                h5_edit.setText(p)

        h5_row = QWidget()
        h5_h = QHBoxLayout(h5_row)
        h5_h.setContentsMargins(0, 0, 0, 0)
        h5_h.addWidget(h5_edit)
        h5_h.addWidget(QPushButton("Browse…", clicked=browse_h5))
        form.addRow("Target H5:", h5_row)
        form.addRow("Max workers:", workers)
        lay.addLayout(form)
        lay.addWidget(qc_cb)
        lay.addWidget(skip_cb)
        lay.addWidget(prof_cb)
        flt = QFormLayout()
        flt.addRow("Filter animal IDs:", fa)
        flt.addRow("Filter sessions:", fs)
        flt.addRow("Filter trials:", ft)
        lay.addLayout(flt)
        log = QPlainTextEdit()
        log.setReadOnly(True)
        lay.addWidget(log)
        worker: Optional[_AnalyzeWorker] = None

        def on_done(ok: bool, msg: str) -> None:
            nonlocal worker
            worker = None
            log.appendPlainText(msg + "\n")
            (QMessageBox.information if ok else QMessageBox.warning)(dlg, "Analyze", msg)

        def run_an() -> None:
            nonlocal worker
            if worker is not None:
                return
            profile = None
            if prof_cb.isChecked():
                profile = (config.analysis_trajectory, config.analysis_trace_quality)
            worker = _AnalyzeWorker(
                db_path=Path(h5_edit.text().strip()),
                generate_qc=qc_cb.isChecked(),
                skip_mistrials=skip_cb.isChecked(),
                max_workers=int(workers.value()),
                animal_ids=_parse_filter_list(fa.text()),
                sessions=_parse_filter_list(fs.text()),
                trials=_parse_filter_list(ft.text()),
                analysis_profile=profile,
            )
            worker.log_line.connect(log.appendPlainText)
            worker.finished_ok.connect(on_done)
            worker.start()

        lay.addWidget(QPushButton("Run pipeline", clicked=run_an))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(560, 480)
        dlg.show()

    def prompt_export_filters(parent: QWidget) -> Optional[Tuple[str, str, str]]:
        dlg = QDialog(parent)
        dlg.setWindowTitle("Export — trial filters (optional)")
        v = QVBoxLayout(dlg)
        form = QFormLayout()
        fa = QLineEdit("")
        fs = QLineEdit("")
        ft = QLineEdit("")
        form.addRow("Animal IDs (comma/space):", fa)
        form.addRow("Sessions (e.g. S01):", fs)
        form.addRow("Trials (e.g. T01):", ft)
        v.addLayout(form)
        v.addWidget(
            QLabel(
                "Leave blank to export all trials. RAM-only H5 exports may need a separate audit."
            )
        )
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return (fa.text().strip(), fs.text().strip(), ft.text().strip())

else:

    def open_discovery_dialog(parent: object, config: object) -> None:
        del parent, config

    def open_inference_dialog(parent: object, config: object) -> None:
        del parent, config

    def open_analyze_dialog(parent: object, config: object) -> None:
        del parent, config

    def prompt_export_filters(parent: object) -> Optional[Tuple[str, str, str]]:
        del parent
        return ("", "", "")
