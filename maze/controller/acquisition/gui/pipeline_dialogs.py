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

    from maze.pipeline.inference_backend import (
        BACKEND_CHOICES,
        BACKEND_KIND_DEEPLABCUT_STUB,
        BACKEND_KIND_SLEAP_NN,
        find_existing_pose_output,
        get_backend,
        is_sleap_nn_available,
        planned_slp_output_path,
    )
    from maze.pipeline.io.file_discovery import TREATMENT_LABELS_HEADER
    from maze.pipeline.treatment_labels_csv import (
        TreatmentLabelsCsvError,
        create_treatment_labels_csv,
        open_treatment_labels_in_system_editor,
        validate_treatment_labels_csv,
    )
    from maze.pipeline.trial_filters import (
        GUI_DEFAULT_PREFILTER_MODE,
        PREFILTER_MODE_DESCRIPTIONS,
        prefilter_mode_summary,
    )

    HAS_QT = True
except ImportError:
    HAS_QT = False
    QThread = object  # type: ignore[misc, assignment]


def _default_h5_path(config: "AcquisitionConfig") -> Path:
    from maze.pipeline.controller_discovery import default_results_h5_path

    return default_results_h5_path(config)


def _default_discovery_dirs_text(config: "AcquisitionConfig") -> str:
    from maze.pipeline.controller_discovery import default_discovery_data_dirs
    from maze.pipeline.paths import DATA_DIRS

    dirs = default_discovery_data_dirs(config)
    if dirs:
        return "; ".join(str(p) for p in dirs)
    return "; ".join(str(p) for p in DATA_DIRS)


def _default_treatment_labels_path(config: "AcquisitionConfig") -> Path:
    from maze.pipeline.controller_discovery import default_treatment_labels_path

    return default_treatment_labels_path(config)


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
            backend_kind: str,
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
            self._backend_kind = backend_kind
            self._animal_ids = animal_ids
            self._sessions = sessions
            self._trials = trials

        def run(self) -> None:
            from maze.pipeline.db import TrialKey, write_sleap_model_path, write_sleap_path
            from maze.pipeline.headless_encode import materialize_xy_tables_from_video
            from maze.pipeline.persist_pose import persist_pose_from_sidecar
            from maze.pipeline.run_pipeline import load_trial_manifests_from_db
            from maze.pipeline.run_provenance import record_provenance, utc_now_iso

            started_at = utc_now_iso()
            try:
                backend = get_backend(self._backend_kind)
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
                    out_path = planned_slp_output_path(vp, self._output_dir)
                    existing = find_existing_pose_output(
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
                        persist_pose_from_sidecar(
                            self._db_path,
                            key,
                            existing,
                            overwrite_pose=False,
                        )
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
                    persist_pose_from_sidecar(
                        self._db_path,
                        key,
                        pred,
                        overwrite_pose=False,
                    )
                    if self._materialize_xy:
                        materialize_xy_tables_from_video(
                            db_path=self._db_path,
                            key=key,
                            video_path=vp,
                            config=self._config,
                            model_dir=str(self._model_path),
                        )
                    n_ok += 1
                record_provenance(
                    anchor=self._db_path,
                    operation="virtual_acquisition",
                    inputs={
                        "db_path": str(self._db_path),
                        "model_path": str(self._model_path),
                        "device": self._device,
                        "batch_size": self._batch_size,
                        "skip_existing": self._skip_existing,
                        "materialize_xy": self._materialize_xy,
                        "output_dir": str(self._output_dir) if self._output_dir else None,
                        "backend_kind": self._backend_kind,
                        "n_trials_with_video": len(with_video),
                    },
                    outputs={"n_ok": n_ok, "n_trials_with_video": len(with_video)},
                    started_at=started_at,
                )
                self.finished_ok.emit(
                    True,
                    f"Virtual acquisition finished ({n_ok}/{len(with_video)} trials processed).",
                )
            except Exception as e:
                self.log_line.emit(traceback.format_exc())
                record_provenance(
                    anchor=self._db_path,
                    operation="virtual_acquisition",
                    inputs={
                        "db_path": str(self._db_path),
                        "model_path": str(self._model_path),
                    },
                    status="failed",
                    error=f"{type(e).__name__}: {e}",
                    started_at=started_at,
                )
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
                        prefilter_mode=GUI_DEFAULT_PREFILTER_MODE,
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
        hint = QLabel(
            "Controller-first: scans the acquisition output folder for "
            "{animal}_{session}_{trial}.mp4 videos and pose sidecars, then syncs paths "
            "into the results H5 (default trials.h5). Set Output folder in Settings if empty."
        )
        hint.setWordWrap(True)
        v.addWidget(hint)
        form = QFormLayout()
        h5_edit = QLineEdit(str(_default_h5_path(config)))
        lbl_edit = QLineEdit(str(_default_treatment_labels_path(config)))

        dirs_edit = QLineEdit(_default_discovery_dirs_text(config))
        dirs_edit.setPlaceholderText(
            "Acquisition output folder (or ; / newline separated roots). "
            "Empty = paths.py DATA_DIRS"
        )
        out_hint = (config.output_dir or "").strip()
        if not out_hint:
            h5_edit.setToolTip("Set Output folder in Settings → acquisition for a default path.")
            dirs_edit.setToolTip("Set Output folder in Settings → acquisition to scan recorded trials.")

        def browse_h5() -> None:
            start = str(Path(h5_edit.text()).parent)
            if not start or start == ".":
                start = out_hint or ""
            p, _ = QFileDialog.getOpenFileName(dlg, "Results H5", start, "H5 (*.h5)")
            if p:
                h5_edit.setText(p)

        def browse_lbl() -> None:
            start = str(Path(lbl_edit.text()).parent)
            p, _ = QFileDialog.getOpenFileName(dlg, "Treatment labels", start, "CSV (*.csv)")
            if p:
                lbl_edit.setText(p)

        def browse_data_dir() -> None:
            d = QFileDialog.getExistingDirectory(
                dlg,
                "Data root for discovery scan",
                out_hint or "",
            )
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
        def _labels_path_from_field() -> Path:
            raw = lbl_edit.text().strip()
            return Path(raw) if raw else _default_treatment_labels_path(config)

        def on_create_labels() -> None:
            path = _labels_path_from_field()
            if path.exists():
                ans = QMessageBox.question(
                    dlg,
                    "Treatment labels",
                    f"{path} already exists. Overwrite with an empty template?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if ans != QMessageBox.StandardButton.Yes:
                    return
                overwrite = True
            else:
                overwrite = False
            try:
                create_treatment_labels_csv(path, overwrite=overwrite)
                lbl_edit.setText(str(path))
                log.appendPlainText(f"Created treatment labels template → {path}\n")
                log.appendPlainText(f"Header: {','.join(TREATMENT_LABELS_HEADER)}\n")
                QMessageBox.information(
                    dlg,
                    "Treatment labels",
                    f"Created {path}. Use “Open in editor…” to fill rows, then Sync.",
                )
            except TreatmentLabelsCsvError as e:
                QMessageBox.warning(dlg, "Treatment labels", str(e))

        def on_open_labels() -> None:
            path = _labels_path_from_field()
            try:
                open_treatment_labels_in_system_editor(path)
                log.appendPlainText(f"Opened in system editor: {path}\n")
            except TreatmentLabelsCsvError as e:
                QMessageBox.warning(dlg, "Treatment labels", str(e))

        create_lbl_btn = QPushButton("Create new…", clicked=on_create_labels)
        create_lbl_btn.setToolTip(
            "Create an empty treatment_labels.csv with the canonical header. "
            "Does not call /orm/discover — edit rows manually or use merge on Sync."
        )
        open_lbl_btn = QPushButton("Open in editor…", clicked=on_open_labels)
        open_lbl_btn.setToolTip("Open the CSV in your default spreadsheet/editor (validates header first).")
        lbl_h.addWidget(create_lbl_btn)
        lbl_h.addWidget(open_lbl_btn)
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
            from maze.pipeline.io.file_discovery import discover_trials
            from maze.pipeline.sources.legacy_vast import check_duplicates

            try:
                dbp = Path(h5_edit.text().strip())
                dd = _parse_data_dirs_text(dirs_edit.text())
                r = discover_trials(
                    dd,
                    exclude_h5_paths=[dbp] if dbp else None,
                    controller_results_h5=dbp if dbp else None,
                )
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
                if lp is not None:
                    validate_treatment_labels_csv(lp)
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
            except TreatmentLabelsCsvError as e:
                QMessageBox.warning(dlg, "Discovery", str(e))
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
        hint = QLabel(
            "Runs batch SLEAP-NN on trials with video paths in the results H5. "
            "Default pose files: <output_dir>/<video_stem>.predictions.slp when Output folder is set, "
            "else beside the video. With skip-existing enabled, trials are not re-inferred when a pose "
            "file is already listed in the H5, planned at the output path, or present as "
            ".predictions.slp / .slp next to the video; sleap_path in the H5 is updated anyway."
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)
        form = QFormLayout()
        h5_edit = QLineEdit(str(_default_h5_path(config)))
        model_edit = QLineEdit((config.sleap_model_path or "").strip())
        out_default = (config.output_dir or "").strip()
        out_edit = QLineEdit(out_default)
        backend_combo = QComboBox()
        for label, kind in BACKEND_CHOICES:
            backend_combo.addItem(label, kind)
        backend_combo.setCurrentIndex(0)
        for i in range(backend_combo.count()):
            if backend_combo.itemData(i) == BACKEND_KIND_DEEPLABCUT_STUB:
                model = backend_combo.model()
                if model is not None:
                    item = model.item(i)
                    if item is not None:
                        item.setEnabled(False)
        dev_edit = QLineEdit("auto")
        batch = QSpinBox()
        batch.setRange(1, 128)
        batch.setValue(4)
        skip_cb = QCheckBox("Skip existing pose outputs (see note above)")
        skip_cb.setChecked(True)
        skip_cb.setToolTip(
            "Checked: reuse existing .slp / .predictions.slp and refresh H5 paths without calling SLEAP-NN. "
            "Unchecked: always run inference (overwrites planned output path)."
        )
        mat_cb = QCheckBox("Materialize spot / in-range / centroid tables (headless encode)")
        mat_cb.setChecked(True)
        fa = QLineEdit("")
        fs = QLineEdit("")
        ft = QLineEdit("")
        if not is_sleap_nn_available():
            backend_combo.setToolTip("Install sleap-nn: uv sync --extra sleap")

        def browse_h5() -> None:
            start = str(Path(h5_edit.text()).parent)
            if not start or start == ".":
                start = out_default or ""
            p, _ = QFileDialog.getOpenFileName(dlg, "Results H5", start, "H5 (*.h5)")
            if p:
                h5_edit.setText(p)

        def browse_model() -> None:
            p = QFileDialog.getExistingDirectory(
                dlg,
                "SLEAP model directory",
                model_edit.text().strip() or out_default or "",
            )
            if p:
                model_edit.setText(p)

        def browse_out() -> None:
            d = QFileDialog.getExistingDirectory(
                dlg,
                "Prediction output directory",
                out_edit.text().strip() or out_default or "",
            )
            if d:
                out_edit.setText(d)

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
        out_row = QWidget()
        out_h = QHBoxLayout(out_row)
        out_h.setContentsMargins(0, 0, 0, 0)
        out_h.addWidget(out_edit)
        out_h.addWidget(QPushButton("Browse…", clicked=browse_out))
        form.addRow("Prediction output dir:", out_row)
        form.addRow("Pose backend:", backend_combo)
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
            kind = str(backend_combo.currentData() or BACKEND_KIND_SLEAP_NN)
            if kind == BACKEND_KIND_DEEPLABCUT_STUB:
                QMessageBox.warning(
                    dlg,
                    "Virtual acquisition",
                    "DeepLabCut backend is not available in this build.",
                )
                return
            if not is_sleap_nn_available():
                QMessageBox.warning(
                    dlg,
                    "Virtual acquisition",
                    "sleap-nn is not installed. Run: uv sync --extra sleap",
                )
                return
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
                backend_kind=kind,
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
        out_hint = (config.output_dir or "").strip()
        hint = QLabel(
            "Runs the ambulation/QC pipeline on trials listed in the results H5. "
            "Controller-first: prefilter mode is fixed to "
            f"“{GUI_DEFAULT_PREFILTER_MODE}” — "
            f"{prefilter_mode_summary(GUI_DEFAULT_PREFILTER_MODE)} "
            "Legacy batch CLI uses prefilter_mode=legacy (see readme.md)."
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)
        form = QFormLayout()
        h5_edit = QLineEdit(str(_default_h5_path(config)))
        prefilter_label = QLabel(
            f"{GUI_DEFAULT_PREFILTER_MODE} — {PREFILTER_MODE_DESCRIPTIONS[GUI_DEFAULT_PREFILTER_MODE]}"
        )
        prefilter_label.setWordWrap(True)
        workers = QSpinBox()
        workers.setRange(1, 32)
        workers.setValue(1)
        qc_cb = QCheckBox("Generate QC images")
        qc_cb.setChecked(True)
        skip_cb = QCheckBox("Skip mistrials (write mistrial_reason for bad inputs)")
        skip_cb.setChecked(True)
        skip_cb.setToolTip(
            "With controller prefilter, mistrials are not auto-detected from missing "
            "legacy inputs; failed trials are usually processing errors. Uncheck to keep "
            "trials that would be marked mistrial under legacy rules."
        )
        prof_cb = QCheckBox("Apply current analysis profile (trajectory + trace quality)")
        prof_cb.setChecked(False)
        fa = QLineEdit("")
        fs = QLineEdit("")
        ft = QLineEdit("")
        if not out_hint:
            h5_edit.setToolTip("Set Output folder in Settings → acquisition for default trials.h5 path.")

        def browse_h5() -> None:
            start = str(Path(h5_edit.text()).parent)
            if not start or start == ".":
                start = out_hint or ""
            p, _ = QFileDialog.getOpenFileName(dlg, "Results H5", start, "H5 (*.h5)")
            if p:
                h5_edit.setText(p)

        h5_row = QWidget()
        h5_h = QHBoxLayout(h5_row)
        h5_h.setContentsMargins(0, 0, 0, 0)
        h5_h.addWidget(h5_edit)
        h5_h.addWidget(QPushButton("Browse…", clicked=browse_h5))
        form.addRow("Target H5:", h5_row)
        form.addRow("Input prefilter:", prefilter_label)
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
