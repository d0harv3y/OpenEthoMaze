"""Trial run timer, session controls, recorder flush, and virtual trial clock."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from ..h5_writer import open_db
from ..shared_controller import config_center_xy
from .analysis_worker import AnalysisWorker
from .camera_loop import is_video_available
from .file_actions import ask_trial_overwrite_merged, next_keep_both_suffix
from .legacy_exit_seed import seed_legacy_exit_for_virtual_start
from maze.pipeline.pose_status import policy_to_overwrite_pose

from .status_and_config_sync import apply_status_and_buttons, apply_ui_to_config

if TYPE_CHECKING:
    from .main_window import MainWindow

try:
    from PySide6.QtCore import Qt, QTimer
except ImportError:
    pass


def virtual_trial_clock_enabled(window: MainWindow) -> bool:
    """True when stretched virtual playback should drive ``trial_elapsed_s`` from frame deltas."""
    v = getattr(window._config, "virtual_duration_override_s", None)
    if v is None or float(v) <= 0:
        return False
    return is_video_available(window) and window._camera_source.currentText().startswith(
        "Virtual"
    )

def compute_trial_clock_virtual_dt_s(
    window: MainWindow, running: bool, prev_running: bool
) -> Optional[float]:
    """
    Seconds of video time to add to ``trial_elapsed_s`` this run-timer tick.

    Returns ``None`` when the trial controller should use wall-clock ``dt`` instead.
    """
    if not virtual_trial_clock_enabled(window):
        if not running:
            window._virtual_trial_clock_last_fi = None
        return None
    cc = window._camera_controller
    if cc is None:
        return None
    eff = cc.virtual_file_effective_fps(window._config)
    if eff is None or eff <= 0:
        return None
    if not running:
        window._virtual_trial_clock_last_fi = None
        return None
    fi, _ = cc.get_last_frame_info()
    if fi is None:
        return 0.0
    fi_i = int(fi)
    last_fi = window._virtual_trial_clock_last_fi
    if not prev_running:
        window._virtual_trial_clock_last_fi = fi_i
        return 0.0
    if last_fi is None:
        window._virtual_trial_clock_last_fi = fi_i
        return 0.0
    dfi = fi_i - int(last_fi)
    if dfi < 0:
        window._virtual_trial_clock_last_fi = fi_i
        return 0.0
    window._virtual_trial_clock_last_fi = fi_i
    return dfi / float(eff)

def on_run_timer(window: MainWindow) -> None:
    now = time.monotonic()
    if window._run_timer_last_s is None:
        window._run_timer_last_s = now
        apply_status_and_buttons(window)
        return
    dt = now - window._run_timer_last_s
    window._run_timer_last_s = now
    if window._last_track_xy is not None:
        x, y = window._last_track_xy
    else:
        # Fall back to arena center instead of (0,0) so duty/exit logic
        # doesn't saturate when tracking is temporarily unavailable.
        x, y = config_center_xy(window._config)
    tc = window._trial_controller
    running = tc.is_trial_running_phase()
    prev_running = window._prev_trial_running_virtual_clock
    trial_clock_dt = compute_trial_clock_virtual_dt_s(window, running, prev_running)
    window._prev_trial_running_virtual_clock = running
    tc.tick(x, y, dt, trial_clock_dt_s=trial_clock_dt)
    apply_status_and_buttons(window)

def on_stop_run(window: MainWindow) -> None:
    if window._arduino_stimulus is not None and window._arduino_stimulus.connected:
        window._arduino_stimulus.set_duty(0)
    if window._run_timer is not None:
        window._run_timer.stop()
        window._run_timer = None
    window._run_timer_last_s = None
    window._prev_trial_running_virtual_clock = False
    window._virtual_trial_clock_last_fi = None
    stop_trial_recorder_if_active(window)
    window._trial_controller.stop_run()
    apply_status_and_buttons(window)

def on_trial_state_change(window: MainWindow, new_state) -> None:
    """When trial ends (SUCCESS or TIMEOUT), advance slot first (so motors stop), then flush/clear recorder (may show duplicate popup)."""
    state_value = getattr(new_state, "value", str(new_state))
    if state_value not in {"trial_success", "trial_timeout"}:
        return
    # Advance trial so state is ITI/IDLE before any modal dialog; motors stop immediately
    window._trial_controller.stop_run()
    if window._arduino_stimulus is not None and window._arduino_stimulus.connected:
        window._arduino_stimulus.set_duty(0)
    apply_status_and_buttons(window)
    stop_trial_recorder_if_active(window)

def stop_trial_recorder_if_active(window: MainWindow) -> None:
    """If a trial recording is in progress, show one overwrite/discard/keep_both dialog for H5 and video conflicts, then stop or cancel."""
    if window._trial_recorder is None:
        return
    rec = window._trial_recorder
    exit_x, exit_y = window._trial_controller.get_exit_position_px()
    timestamp_str = datetime.now(timezone.utc).isoformat(timespec="seconds")
    existing_h5_key = f"/{rec.animal_id}/{rec.session_id}/{rec.trial}"
    final_video_path = rec.output_dir / f"{rec.animal_id}_{rec.session_id}_{rec.trial}.mp4"

    h5_conflict = False
    if rec.db_path.exists():
        try:
            with open_db(rec.db_path, "r") as h5:
                if existing_h5_key in h5:
                    h5_conflict = True
        except Exception:
            pass
    video_conflict = final_video_path.exists()

    conflict_choice = None
    if h5_conflict or video_conflict:
        suffix = next_keep_both_suffix(
            rec.db_path,
            rec.output_dir,
            rec.animal_id,
            rec.session_id,
            rec.trial,
        )
        new_h5_key = f"/{rec.animal_id}/{rec.session_id}/{rec.trial}{suffix}"
        new_video_path = (
            rec.output_dir / f"{rec.animal_id}_{rec.session_id}_{rec.trial}{suffix}.mp4"
        )
        choice = ask_trial_overwrite_merged(
            window,
            h5_key=existing_h5_key if h5_conflict else None,
            video_path=final_video_path if video_conflict else None,
            new_h5_key_with_suffix=new_h5_key,
            new_video_path_with_suffix=new_video_path,
            keep_both_suffix=suffix,
        )
        if choice == "discard":
            try:
                rec.cancel(delete_video=True)
            except Exception:
                pass
            window._trial_recorder = None
            window._record_frame_index = 0
            return
        if choice != "overwrite":
            _, suffix = choice
            _, suffix_from_choice = choice
            rec.trial = rec.trial + (suffix_from_choice or "(2)")
        # Pass choice to recorder so it renames video to the right path (overwrite vs keep_both with new trial path)
        conflict_choice = choice if (video_conflict or choice != "overwrite") else None

    stop_ok = False
    try:
        rec.stop(
            exit_x_px=exit_x,
            exit_y_px=exit_y,
            timestamp_str=timestamp_str,
            conflict_choice=conflict_choice,
        )
        stop_ok = True
    except Exception as e:
        import traceback

        print(f"Error in TrialRecorder.stop: {e}")
        traceback.print_exc()
    # Capture trial info only when stop() succeeded, so analysis runs on a trial that was actually written
    run_analysis = window._config.run_analysis_after_trial
    if run_analysis and stop_ok:
        captured = (
            rec.db_path,
            rec.animal_id,
            rec.session_id,
            rec.trial,
            getattr(rec, "_video_path", None),
            window._config.run_phase or "habituation",
        )
    else:
        captured = None
    window._trial_recorder = None
    window._record_frame_index = 0

    # Start pipeline analysis in background if enabled and no worker already running
    if captured and window._analysis_worker is None and AnalysisWorker is not None:
        db_path, animal_id, session_id, trial, video_path, run_phase = captured
        window._analysis_worker = AnalysisWorker(
            db_path=db_path,
            animal_id=animal_id,
            session_id=session_id,
            trial=trial,
            video_path=video_path,
            run_phase=run_phase,
            analysis_profile=(
                window._config.analysis_trajectory,
                window._config.analysis_trace_quality,
            ),
            overwrite_pose=policy_to_overwrite_pose(window._config.pose_overwrite_policy),
        )
        window._analysis_worker.finished.connect(
            window._on_analysis_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        window._analysis_worker.start()
        window.statusBar().showMessage("Analyzing trial…")

def on_start_trial(window: MainWindow) -> None:
    if not window._dev_mode:
        if not is_video_available(window):
            window.statusBar().showMessage("Start camera before running trials.")
            return
        virtual_mode = (
            window._camera_source.currentText().startswith("Virtual")
            and is_video_available(window)
        )
        if (
            window._task_spec.requires_mc_connection
            and not window._is_mc_connected()
            and not virtual_mode
        ):
            window.statusBar().showMessage("Connect MC before running trials.")
            return
    apply_ui_to_config(window)
    sid = window._session_id_edit.text().strip()
    lookup_status: Optional[str] = None

    # In virtual mode, Start trial seeks to the scrubber position (or frame 0).
    if (
        window._camera_source.currentText().startswith("Virtual")
        and window._camera_controller is not None
    ):
        try:
            start_f = 0
            if hasattr(window, "_virtual_scrub_row_w") and window._virtual_scrub_row_w.isVisible():
                start_f = int(window._virtual_scrub_slider.value())
            window._camera_controller.seek_video_frame(start_f)
            window._virtual_has_initial_frame = False
            window._virtual_cached_frame_raw = None
            window._virtual_cached_frame_index = None
        except Exception:
            # Best-effort only; if seek fails, playback will continue from current position.
            pass

    legacy_status = seed_legacy_exit_for_virtual_start(window)
    if legacy_status is not None:
        lookup_status = legacy_status

    if (
        window._camera_source.currentText().startswith("Virtual")
        and window._playback_hydration is not None
    ):
        sid = window._playback_hydration.session_id or sid
        if hasattr(window._trial_controller, "clear_legacy_exit_xy"):
            window._trial_controller.clear_legacy_exit_xy()
        if window._playback_hydration.legacy_exit_xy is not None and hasattr(
            window._trial_controller, "set_legacy_exit_xy"
        ):
            window._trial_controller.set_legacy_exit_xy(
                window._playback_hydration.legacy_exit_xy[0],
                window._playback_hydration.legacy_exit_xy[1],
            )
        window._trial_controller.reset(
            sid,
            trial_idx=window._playback_hydration.trial_idx,
            slot_idx=window._playback_hydration.slot_idx,
        )

    msg = window._trial_controller.do_start(sid, lookup_status=lookup_status)
    apply_status_and_buttons(window)
    window.statusBar().showMessage(msg)
    if window._trial_controller.run_active:
        if window._run_timer is None or not window._run_timer.isActive():
            window._run_timer = QTimer(window)
            window._run_timer.timeout.connect(window._on_run_timer)
            window._run_timer.start(window._run_timer_interval_ms)
            window._run_timer_last_s = None
    else:
        if window._run_timer is not None and window._run_timer.isActive():
            window._run_timer.stop()
            window._run_timer = None
        window._run_timer_last_s = None

def on_previous_trial(window: MainWindow) -> None:
    if not window._dev_mode:
        if not is_video_available(window):
            window.statusBar().showMessage("Start camera before running trials.")
            return
        virtual_mode = (
            window._camera_source.currentText().startswith("Virtual")
            and is_video_available(window)
        )
        if (
            window._task_spec.requires_mc_connection
            and not window._is_mc_connected()
            and not virtual_mode
        ):
            window.statusBar().showMessage("Connect MC before running trials.")
            return
    sid = window._session_id_edit.text().strip()
    msg = window._trial_controller.do_previous(sid)
    apply_status_and_buttons(window)
    window.statusBar().showMessage(msg)

def on_next_trial(window: MainWindow) -> None:
    if not window._dev_mode:
        if not is_video_available(window):
            window.statusBar().showMessage("Start camera before running trials.")
            return
        virtual_mode = (
            window._camera_source.currentText().startswith("Virtual")
            and is_video_available(window)
        )
        if (
            window._task_spec.requires_mc_connection
            and not window._is_mc_connected()
            and not virtual_mode
        ):
            window.statusBar().showMessage("Connect MC before running trials.")
            return
    sid = window._session_id_edit.text().strip()
    msg = window._trial_controller.do_next(sid)
    apply_status_and_buttons(window)
    window.statusBar().showMessage(msg)

def on_session_controls_changed(window: MainWindow) -> None:
    """Sync phase, mode and session ID from UI; reset to first trial on any change."""
    sid = window._session_id_edit.text().strip()
    p = window._phase_combo.currentData()
    if p is not None and window._task_spec.set_phase_value is not None:
        window._task_spec.set_phase_value(window._config, str(p))
    m = window._mode_combo.currentData()
    if m is not None:
        window._task_spec.set_mode_value(window._config, str(m))
    window._trial_controller.apply_session_controls(sid)
    apply_status_and_buttons(window)

