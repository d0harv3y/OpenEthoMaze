from __future__ import annotations

from maze.controller.local_service_launcher import (
    is_waitress_available,
    waitress_unavailable_message,
)
from maze.kpms.availability import is_kpms_available
from maze.pipeline.inference_backend import is_sleap_nn_available
from maze.pipeline.viz.overlay_cli import is_unified_overlay_available


def build_main_window_menus(
    window,
    *,
    reload_last_profile_checked: bool,
    pipeline_dialogs_available: bool = True,
    sleap_inference_available: bool | None = None,
    kpms_fit_dialog_available: bool = False,
    kpms_apply_dialog_available: bool = False,
    qc_summary_dialog_available: bool = False,
    overlay_dialog_available: bool = False,
) -> None:
    """Build the main window menus while keeping ``MainWindow`` as composition root."""
    menubar = window.menuBar()
    file_menu = menubar.addMenu("&File")
    window._reload_last_profile_action = file_menu.addAction("Reload last profile(s) on startup")
    window._reload_last_profile_action.setCheckable(True)
    window._reload_last_profile_action.setChecked(reload_last_profile_checked)
    window._reload_last_profile_action.triggered.connect(window._on_toggle_reload_last_profile)
    file_menu.addSeparator()
    file_menu.addAction("Load acquisition profile…", window._on_load_profile)
    file_menu.addAction("Save acquisition profile", window._on_save_profile)
    file_menu.addAction("Save acquisition profile as…", window._on_save_profile_as)
    file_menu.addAction("Open acquisition profile in editor", window._on_open_profile_in_editor)
    file_menu.addAction("Reload acquisition profile", window._on_reload_profile)
    file_menu.addSeparator()
    file_menu.addAction("Open current DB in h5web", window._on_open_current_db_h5web)
    file_menu.addAction("Open H5 in h5web…", window._on_open_h5web)
    window._start_local_service_action = file_menu.addAction(
        "Start local ORM service…",
        window._on_start_local_service,
    )
    window._start_local_service_action.setEnabled(is_waitress_available())
    if is_waitress_available():
        window._start_local_service_action.setToolTip(
            "Spawn maze-local-service in a subprocess (h5web + /orm/* on localhost)."
        )
    else:
        window._start_local_service_action.setToolTip(waitress_unavailable_message())
    file_menu.addSeparator()
    file_menu.addAction("Exit", window._on_file_exit)

    settings_menu = menubar.addMenu("&Settings")
    settings_menu.addAction("acquisition…", window._on_settings)
    settings_menu.addAction("analysis…", window._on_analysis_settings)

    pipeline_menu = menubar.addMenu("&Pipeline")
    discovery_action = pipeline_menu.addAction("Discovery…", window._on_pipeline_discovery)
    discovery_action.setEnabled(pipeline_dialogs_available)
    if pipeline_dialogs_available:
        discovery_action.setToolTip(
            "Scan acquisition output folder and sync trial manifest into trials.h5. "
            "Requires Output folder in Settings → acquisition (or choose paths in the dialog)."
        )
    else:
        discovery_action.setToolTip("Pipeline dialogs unavailable (PySide6 / import error).")
    if sleap_inference_available is None:
        sleap_inference_available = is_sleap_nn_available()
    inference_enabled = pipeline_dialogs_available and sleap_inference_available
    inference_action = pipeline_menu.addAction(
        "Virtual acquisition…", window._on_pipeline_inference
    )
    inference_action.setEnabled(inference_enabled)
    if inference_enabled:
        inference_action.setToolTip(
            "Batch SLEAP-NN pose inference for trials with video in the results H5. "
            "Requires --extra sleap and a model directory with best.ckpt."
        )
    elif not pipeline_dialogs_available:
        inference_action.setToolTip("Pipeline dialogs unavailable (PySide6 / import error).")
    else:
        inference_action.setToolTip(
            "SLEAP-NN not installed. Run: uv sync --extra sleap (see readme.md)."
        )
    analyze_action = pipeline_menu.addAction("Analyze…", window._on_pipeline_analyze)
    analyze_action.setEnabled(pipeline_dialogs_available)
    if pipeline_dialogs_available:
        analyze_action.setToolTip(
            "Run ambulation/QC on trials in the results H5. "
            "Uses prefilter_mode=controller (no legacy frame-diff or missing-file gates). "
            "CLI legacy batch: maze-legacy-db run with prefilter_mode=legacy."
        )
    else:
        analyze_action.setToolTip("Pipeline dialogs unavailable (PySide6 / import error).")
    kpms_fit_enabled = kpms_fit_dialog_available and is_kpms_available()
    kpms_fit_action = pipeline_menu.addAction("kpMS fit…", window._on_pipeline_kpms_fit)
    kpms_fit_action.setEnabled(kpms_fit_enabled)
    if kpms_fit_enabled:
        kpms_fit_action.setToolTip(
            "Fit a keypoint-MoSeq model from a trial manifest CSV (slow; --extra kpms). "
            "Writes checkpoint and results under the project directory."
        )
    elif not kpms_fit_dialog_available:
        kpms_fit_action.setToolTip("kpMS fit dialog unavailable (PySide6 / import error).")
    else:
        kpms_fit_action.setToolTip(
            "keypoint-moseq is not installed. Run: uv sync --extra kpms"
        )
    kpms_apply_enabled = kpms_apply_dialog_available and is_kpms_available()
    kpms_apply_action = pipeline_menu.addAction("kpMS apply…", window._on_pipeline_kpms_apply)
    kpms_apply_action.setEnabled(kpms_apply_enabled)
    if kpms_apply_enabled:
        kpms_apply_action.setToolTip(
            "Apply a trained keypoint-MoSeq checkpoint to trials in a manifest CSV (--extra kpms). "
            "Requires a prior fit; writes results_apply.h5 and apply_summary.json."
        )
    elif not kpms_apply_dialog_available:
        kpms_apply_action.setToolTip("kpMS apply dialog unavailable (PySide6 / import error).")
    else:
        kpms_apply_action.setToolTip(
            "keypoint-moseq is not installed. Run: uv sync --extra kpms"
        )
    qc_action = pipeline_menu.addAction("QC summary…", window._on_pipeline_qc_summary)
    qc_action.setEnabled(qc_summary_dialog_available)
    if qc_summary_dialog_available:
        qc_action.setToolTip(
            "Mistrial counts by reason, analyze coverage, and QC image presence "
            "for a results H5. Export mistrial CSV with suggested fixes."
        )
    else:
        qc_action.setToolTip("QC summary dialog unavailable (PySide6 / import error).")
    overlay_enabled = overlay_dialog_available and is_unified_overlay_available()
    overlay_action = pipeline_menu.addAction(
        "Render unified overlay…", window._on_pipeline_render_overlay
    )
    overlay_action.setEnabled(overlay_enabled)
    if overlay_enabled:
        overlay_action.setToolTip(
            "Render one trial MP4 (video + pipeline H5 + optional kpMS). "
            "CLI: uv run maze-render-trial-overlay --help"
        )
    elif not overlay_dialog_available:
        overlay_action.setToolTip("Overlay dialog unavailable (PySide6 / import error).")
    else:
        overlay_action.setToolTip(
            "OpenCV not installed. Install opencv-python (gui extra) to render overlays."
        )
    pipeline_menu.addAction("Export…", window._on_run_exports)

    help_menu = menubar.addMenu("&Help")
    help_menu.addAction("View error log", window._on_view_error_log)
    help_menu.addAction("Open log folder", window._on_open_log_folder)
