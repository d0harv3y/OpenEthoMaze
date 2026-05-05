from __future__ import annotations


def build_main_window_menus(window, *, reload_last_profile_checked: bool) -> None:
    """Build the main window menus while keeping ``MainWindow`` as composition root."""
    menubar = window.menuBar()
    file_menu = menubar.addMenu("&File")
    window._reload_last_profile_action = file_menu.addAction(
        "Reload last profile(s) on startup"
    )
    window._reload_last_profile_action.setCheckable(True)
    window._reload_last_profile_action.setChecked(reload_last_profile_checked)
    window._reload_last_profile_action.triggered.connect(
        window._on_toggle_reload_last_profile
    )
    file_menu.addSeparator()
    file_menu.addAction("Load acquisition profile…", window._on_load_profile)
    file_menu.addAction("Save acquisition profile", window._on_save_profile)
    file_menu.addAction("Save acquisition profile as…", window._on_save_profile_as)
    file_menu.addAction("Open acquisition profile in editor", window._on_open_profile_in_editor)
    file_menu.addAction("Reload acquisition profile", window._on_reload_profile)
    file_menu.addSeparator()
    export_action = file_menu.addAction("Run exports…", window._on_run_exports)
    export_action.setEnabled(getattr(window, "_task_mode", "vast") == "vast")
    file_menu.addAction("Open current DB in h5web", window._on_open_current_db_h5web)
    file_menu.addAction("Open H5 in h5web…", window._on_open_h5web)
    file_menu.addSeparator()
    file_menu.addAction("Exit", window._on_file_exit)

    settings_menu = menubar.addMenu("&Settings")
    settings_menu.addAction("acquisition…", window._on_settings)
    settings_menu.addAction("analysis…", window._on_analysis_settings)

    help_menu = menubar.addMenu("&Help")
    help_menu.addAction("View error log", window._on_view_error_log)
    help_menu.addAction("Open log folder", window._on_open_log_folder)
