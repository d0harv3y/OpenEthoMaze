"""Pipeline menu handlers (discovery, inference, analyze, kpMS, QC, overlay, export)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import MainWindow

try:
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    HAS_QT = True
except ImportError:
    HAS_QT = False

try:
    from .kpms_apply_dialog import HAS_KPMS_APPLY_DIALOG, open_kpms_apply_dialog
except ImportError:
    HAS_KPMS_APPLY_DIALOG = False
    open_kpms_apply_dialog = None  # type: ignore[misc, assignment]

try:
    from .kpms_fit_dialog import HAS_KPMS_FIT_DIALOG, open_kpms_fit_dialog
except ImportError:
    HAS_KPMS_FIT_DIALOG = False
    open_kpms_fit_dialog = None  # type: ignore[misc, assignment]

try:
    from .overlay_dialog import HAS_OVERLAY_DIALOG, open_overlay_dialog
except ImportError:
    HAS_OVERLAY_DIALOG = False
    open_overlay_dialog = None  # type: ignore[misc, assignment]

try:
    from .qc_summary_dialog import HAS_QC_SUMMARY_DIALOG, open_qc_summary_dialog
except ImportError:
    HAS_QC_SUMMARY_DIALOG = False
    open_qc_summary_dialog = None  # type: ignore[misc, assignment]

try:
    from .pipeline_dialogs import (
        HAS_PIPELINE_DIALOGS,
        open_analyze_dialog,
        open_discovery_dialog,
        open_inference_dialog,
        prompt_export_filters,
    )
except ImportError:
    open_analyze_dialog = None  # type: ignore[misc, assignment]
    open_discovery_dialog = None  # type: ignore[misc, assignment]
    open_inference_dialog = None  # type: ignore[misc, assignment]
    prompt_export_filters = None  # type: ignore[misc, assignment]
    HAS_PIPELINE_DIALOGS = False


def on_pipeline_discovery(window: MainWindow) -> None:
    if not HAS_QT or not HAS_PIPELINE_DIALOGS or open_discovery_dialog is None:
        return
    open_discovery_dialog(window, window._config)


def on_pipeline_inference(window: MainWindow) -> None:
    if not HAS_QT or not HAS_PIPELINE_DIALOGS or open_inference_dialog is None:
        return
    open_inference_dialog(window, window._config)


def on_pipeline_analyze(window: MainWindow) -> None:
    if not HAS_QT or not HAS_PIPELINE_DIALOGS or open_analyze_dialog is None:
        return
    open_analyze_dialog(window, window._config)


def on_pipeline_kpms_fit(window: MainWindow) -> None:
    if not HAS_QT or not HAS_KPMS_FIT_DIALOG or open_kpms_fit_dialog is None:
        return
    open_kpms_fit_dialog(window, window._config)


def on_pipeline_kpms_apply(window: MainWindow) -> None:
    if not HAS_QT or not HAS_KPMS_APPLY_DIALOG or open_kpms_apply_dialog is None:
        return
    open_kpms_apply_dialog(window, window._config)


def on_pipeline_qc_summary(window: MainWindow) -> None:
    if not HAS_QT or not HAS_QC_SUMMARY_DIALOG or open_qc_summary_dialog is None:
        return
    open_qc_summary_dialog(window, window._config)


def on_pipeline_render_overlay(window: MainWindow) -> None:
    if not HAS_QT or not HAS_OVERLAY_DIALOG or open_overlay_dialog is None:
        return
    open_overlay_dialog(window, window._config)


def on_run_exports(window: MainWindow) -> None:
    """Run CSV exports on one or more trial databases."""
    if not HAS_QT:
        return
    default_dir = window._config.output_dir or ""
    h5_name = (window._config.h5_filename or "trials.h5").strip() or "trials.h5"
    if Path(h5_name).name != h5_name:
        h5_name = Path(h5_name).name
    start_path = str(Path(default_dir) / h5_name) if default_dir else ""

    paths, _ = QFileDialog.getOpenFileNames(
        window,
        "Select results H5 file(s)",
        start_path,
        "HDF5 (*.h5 *.hdf5);;All (*)",
    )
    if not paths:
        return

    out_dir_str = QFileDialog.getExistingDirectory(
        window,
        "Select output folder for combined exports",
        default_dir or "",
    )
    if not out_dir_str:
        return
    out_dir = Path(out_dir_str)

    animal_f = sess_f = trial_f = ""
    if HAS_PIPELINE_DIALOGS and prompt_export_filters is not None:
        flt = prompt_export_filters(window)
        if flt is None:
            return
        animal_f, sess_f, trial_f = flt

    from maze.pipeline.exports.csv_trials import export_all_for_dbs

    try:
        db_paths = [Path(p) for p in paths]
        exports = export_all_for_dbs(
            db_paths=db_paths,
            output_dir=out_dir,
            include_mistrials=False,
            animal_ids=animal_f or None,
            sessions=sess_f or None,
            trial_names=trial_f or None,
        )
        task_suffixes = {name.rsplit("_", 1)[-1] for name in exports.keys() if "_" in name}
        if len(task_suffixes) > 1:
            QMessageBox.warning(
                window,
                "Export",
                "Mixed tasks detected. Export generated separate CSV files per task "
                f"in {out_dir}.",
            )
        window.statusBar().showMessage(f"Exports completed → {out_dir}")
    except Exception as e:
        window.statusBar().showMessage(f"Exports failed: {e}")
