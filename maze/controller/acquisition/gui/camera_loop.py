"""Camera preview timer loop: virtual scrub, start/stop, per-frame tick."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

import numpy as np

from ..playback_loader import load_playback_hydration
from ..recording import TrialRecorder
from ..radial_arm.config import RadialArmControllerConfig
from ..shared_controller import config_tracking_roi
from .overlay_helpers import (
    draw_roi_and_tracking_overlay,
    resolve_exit_success_override,
)
from .qt_preview import frame_to_pixmap
from .status_and_config_sync import apply_status_and_buttons

if TYPE_CHECKING:
    from .main_window import MainWindow

try:
    from PySide6.QtWidgets import QFileDialog
    from PySide6.QtCore import Qt, QTimer
except ImportError:
    pass

try:
    import cv2 as _cv2
    from ..camera import HAS_CAMERA, apply_display_adjustments
except (ImportError, RuntimeError):
    _cv2 = None
    HAS_CAMERA = False

try:
    from ..tracking import AdaptiveThresholdTracker

    HAS_TRACKING = True
except ImportError:
    AdaptiveThresholdTracker = None
    HAS_TRACKING = False


def reset_sleap_node_jump_state(window: MainWindow) -> None:
    """Clear GUI-side SLEAP node max-jump memory (``_last_pose_xy`` and per-node streaks)."""
    window._pose_jump_state.reset()

def invalidate_tracker_cache(window: MainWindow) -> None:
    reset_sleap_node_jump_state(window)
    if window._tracking_controller is not None:
        path = window._config.sleap_model_path or ""
        window._tracking_controller.set_tracker_sources(
            path.strip(),
            bool(getattr(window._config, "track_enable_backup", True)),
            bool(getattr(window._config, "track_enable_sleap", True)),
        )

def update_pose_last_and_valid(
    window: MainWindow,
    pose_xy: Optional[np.ndarray],
    node_max_jump_px: float,
    node_jump_confirm_frames: int,
) -> Optional[np.ndarray]:
    """Update ``_last_pose_xy``; return per-node validity (finite and within max jump, or debounced).

    When ``node_max_jump_px > 0``, a node that moves farther than that vs the last accepted
    position is marked invalid for up to ``node_jump_confirm_frames - 1`` consecutive frames.
    After that many consecutive over-threshold frames, all jump state is reset from the
    current pose (same effect as Apply). ``node_jump_confirm_frames == 1`` resets on the
    first over-threshold frame.
    """
    return window._pose_jump_state.update(
        pose_xy=pose_xy,
        node_max_jump_px=node_max_jump_px,
        node_jump_confirm_frames=node_jump_confirm_frames,
    )

def on_virtual_scrub_changed(window: MainWindow, value: int) -> None:
    if getattr(window._trial_controller, "run_active", False):
        return
    if window._camera_controller is None:
        return
    window._camera_controller.seek_video_frame(int(value))
    window._virtual_has_initial_frame = False
    window._virtual_cached_frame_raw = None
    window._virtual_cached_frame_index = None

def on_camera_tick(window: MainWindow) -> None:
    if window._camera_controller is None:
        return
    virtual_mode = bool(
        window._camera_source.currentText().startswith("Virtual")
        if window._camera_source is not None
        else False
    )
    tc = window._trial_controller

    # Virtual pause behavior:
    # - when not running, freeze *video advancement* but still re-render overlays
    #   from the cached first frame so settings changes take effect immediately.
    paused_virtual = virtual_mode and not tc.run_active
    if paused_virtual:
        if window._virtual_cached_frame_raw is None:
            t0 = time.perf_counter()
            img_raw = window._camera_controller.grab_frame()
            t1 = time.perf_counter()
            if img_raw is None:
                return
            window._virtual_cached_frame_raw = img_raw
            window._virtual_has_initial_frame = True
            window._virtual_cached_frame_index, _ = window._camera_controller.get_last_frame_info()
        else:
            img_raw = window._virtual_cached_frame_raw
            t0 = time.perf_counter()
            t1 = t0
    else:
        # When running, discard any paused cache so playback resumes from the camera.
        window._virtual_has_initial_frame = False
        window._virtual_cached_frame_raw = None
        window._virtual_cached_frame_index = None
        window._last_virtual_playback_frame_idx = None
        t0 = time.perf_counter()
        img_raw = window._camera_controller.grab_frame()
        t1 = time.perf_counter()
    if img_raw is not None:
        if virtual_mode:
            # In virtual mode, the cached paused frame will be used while paused.
            # When running, the cache was cleared above.
            pass
        # Display FPS (rolling average)
        now = time.monotonic()
        window._display_fps_times.append(now)
        if len(window._display_fps_times) > window._display_fps_max_samples:
            window._display_fps_times.pop(0)
        if len(window._display_fps_times) >= 2:
            span = window._display_fps_times[-1] - window._display_fps_times[0]
            fps = (len(window._display_fps_times) - 1) / span if span > 0 else 0
            window._last_display_fps = float(fps)
            window._track_display_fps_label.setText(f"{fps:.1f}")
        else:
            window._track_display_fps_label.setText("—")

        # Frame index indicator (use camera controller's last seen info).
        if hasattr(window, "_frame_counter_label") and window._frame_counter_label is not None:
            if virtual_mode:
                # Trial-relative: before Start trial, show 0 even if we already grabbed a cached preview frame.
                cur_idx, total = window._camera_controller.get_last_frame_info()
                if not tc.run_active:
                    if total is not None and total > 0:
                        window._frame_counter_label.setText(f"0/{total}")
                    else:
                        window._frame_counter_label.setText("0/—")
                elif cur_idx is None or cur_idx < 0:
                    window._frame_counter_label.setText("—")
                else:
                    cur_1b = cur_idx + 1
                    if total is not None and total > 0:
                        window._frame_counter_label.setText(f"{cur_1b}/{total}")
                    else:
                        window._frame_counter_label.setText(f"{cur_1b}/—")
            else:
                window._frame_counter_label.setText("—")
            if hasattr(window, "_virtual_scrub_row_w") and virtual_mode:
                cur_idx, total = window._camera_controller.get_last_frame_info()
                if total is not None and total > 0:
                    window._virtual_scrub_row_w.setVisible(True)
                    window._virtual_scrub_slider.blockSignals(True)
                    window._virtual_scrub_slider.setMaximum(max(0, int(total) - 1))
                    if not window._virtual_scrub_slider.isSliderDown():
                        v = 0 if (cur_idx is None or cur_idx < 0) else int(cur_idx)
                        v = max(0, min(window._virtual_scrub_slider.maximum(), v))
                        window._virtual_scrub_slider.setValue(v)
                    window._virtual_scrub_slider.blockSignals(False)
                    cur_disp = window._virtual_scrub_slider.value()
                    window._virtual_scrub_label.setText(f"{cur_disp + 1} / {total}")
                else:
                    window._virtual_scrub_row_w.setVisible(False)
            elif hasattr(window, "_virtual_scrub_row_w"):
                window._virtual_scrub_row_w.setVisible(False)
        _tp = time.perf_counter()
        # Raw frame for inference (no brightness/contrast); display uses a copy with adjustments
        flip_now = window._camera_flip.isChecked()
        if (
            window._last_preview_flip_checked is not None
            and flip_now != window._last_preview_flip_checked
        ):
            reset_sleap_node_jump_state(window)
        window._last_preview_flip_checked = flip_now
        if flip_now and _cv2 is not None:
            img_raw = _cv2.flip(img_raw, 1)  # 1 = horizontal (flip x-axis)
        h, w = img_raw.shape[0], img_raw.shape[1]
        window._last_preview_img_size = (w, h)
        window._last_eyedropper_frame_bgr = img_raw
        # Virtual file playback: frame index went backward → video looped or seek; reset GUI pose-jump state.
        if virtual_mode and not paused_virtual and window._camera_controller is not None:
            playback_cur_idx, _ = window._camera_controller.get_last_frame_info()
            if (
                playback_cur_idx is not None
                and window._last_virtual_playback_frame_idx is not None
            ):
                if playback_cur_idx < window._last_virtual_playback_frame_idx:
                    reset_sleap_node_jump_state(window)
            if playback_cur_idx is not None:
                window._last_virtual_playback_frame_idx = playback_cur_idx
        preprocess_ms = (time.perf_counter() - _tp) * 1000.0
        _tp = time.perf_counter()
        # Display copy: brightness/contrast and BGR for overlay
        img_display = apply_display_adjustments(
            img_raw.copy(),
            window._display_brightness.value(),
            window._display_contrast.value(),
        )
        if _cv2 is not None and img_display.ndim == 2:
            img_display = _cv2.cvtColor(img_display, _cv2.COLOR_GRAY2BGR)
        display_prep_ms = (time.perf_counter() - _tp) * 1000.0
        _tp = time.perf_counter()
        show_track = (
            window._config.track_show and HAS_TRACKING and AdaptiveThresholdTracker is not None
        )
        roi_cx, roi_cy, roi_r = config_tracking_roi(window._config)
        roi_center = (roi_cx, roi_cy) if roi_r > 0 else None
        track_xy, track_valid = None, False
        track_source = "fallback"
        pose_xy, pose_scores, pose_edge_inds, pose_node_names = None, None, None, None
        pose_node_valid_from_res = (
            None  # per-node confidence validity from tracker (SLEAP only)
        )
        blob_mask = None
        blob_crop_rect = None
        in_range_xy_res = None
        ram_polys_preview = None
        ram_exit_preview = None
        ram_all_holes_preview = None
        ram_escape_arm_preview = 0
        if window._task_mode == "ram" and isinstance(window._config, RadialArmControllerConfig):
            from ..ram_preview_mask import (
                ram_all_arm_holes_xyr_px,
                ram_exit_hole_xyr_px,
                ram_template_polylines_image,
            )

            ram_polys_preview = ram_template_polylines_image(window._config)
            ram_exit_preview = ram_exit_hole_xyr_px(window._config)
            ram_all_holes_preview = ram_all_arm_holes_xyr_px(window._config)
            sm = tc.get_state_machine() if tc is not None else None
            if sm is not None:
                ram_escape_arm_preview = int(getattr(sm, "exit_arm_index", 0))
            else:
                ram_escape_arm_preview = int(window._config.radial_arm.exit_arm_index)
        ram_template_ms = (time.perf_counter() - _tp) * 1000.0
        _tp = time.perf_counter()
        if show_track and window._tracking_controller is not None:
            enable_backup = bool(getattr(window._config, "track_enable_backup", True))
            enable_sleap = bool(getattr(window._config, "track_enable_sleap", True))
            to_track = img_raw  # inference sees raw image (no brightness/contrast)
            track_r = (
                window._config.arena.tracking_mask_radius_px
                if hasattr(window._config, "arena")
                else roi_r
            )
            did_crop = False
            crop_x0, crop_y0 = 0, 0  # offset to add to tracker coords when we crop
            ram_mask_result = None
            # Only build masked/cropped fallback input when backup tracker is enabled.
            if (
                enable_backup
                and _cv2 is not None
                and window._task_mode == "ram"
                and isinstance(window._config, RadialArmControllerConfig)
            ):
                from ..ram_preview_mask import ram_walkable_mask_crop

                ram_mask_result = ram_walkable_mask_crop(window._config, h, w)
            if ram_mask_result is not None:
                mask_crop, crop_x0, crop_y0, crop_x1, crop_y1 = ram_mask_result
                did_crop = True
                to_track = img_raw[crop_y0:crop_y1, crop_x0:crop_x1].copy()
                to_track = _cv2.bitwise_and(to_track, to_track, mask=mask_crop)
            elif enable_backup and _cv2 is not None and track_r > 0:
                # Crop to rectangle around circle so tracker runs on fewer pixels (better FPS).
                # Display still shows full image; we add crop offset to track_xy/pose_xy and embed blob_mask.
                crop_x0 = max(0, int(roi_cx - track_r) - 1)
                crop_y0 = max(0, int(roi_cy - track_r) - 1)
                crop_x1 = min(w, int(roi_cx + track_r) + 2)
                crop_y1 = min(h, int(roi_cy + track_r) + 2)
                if crop_x1 > crop_x0 and crop_y1 > crop_y0:
                    did_crop = True
                    to_track = img_raw[crop_y0:crop_y1, crop_x0:crop_x1].copy()
                    # Apply circular mask within crop (center relative to crop)
                    cx_crop = roi_cx - crop_x0
                    cy_crop = roi_cy - crop_y0
                    mask_crop = np.zeros(to_track.shape[:2], dtype=np.uint8)
                    _cv2.circle(
                        mask_crop,
                        (int(cx_crop), int(cy_crop)),
                        int(track_r),
                        255,
                        -1,
                    )
                    to_track = _cv2.bitwise_and(to_track, to_track, mask=mask_crop)
            # Update SLEAP parameters on the controller and submit frame
            path = window._config.sleap_model_path or ""
            window._tracking_controller.set_tracker_sources(
                path.strip(),
                enable_backup,
                enable_sleap,
            )
            now = time.monotonic()
            window._tracking_controller.submit_frame(
                to_track,
                now,
                sleap_image=img_raw,
            )
            overlay_state = window._tracking_controller.get_overlay_state(now_s=now)
            track_xy_res = overlay_state["track_xy"]
            track_valid_res = overlay_state["track_valid"]
            track_source = overlay_state["track_source"]
            pose_xy = overlay_state["pose_xy"]
            pose_scores = overlay_state["pose_scores"]
            pose_edge_inds = overlay_state["pose_edge_inds"]
            pose_node_names = overlay_state["pose_node_names"]
            pose_node_valid_from_res = overlay_state["pose_node_valid"]
            blob_mask_res = overlay_state["blob_mask"]
            in_range_xy_res = overlay_state.get("in_range_xy")
            # If we cropped, convert from crop coords to full-image coords.
            # Pass small blob_mask + crop rect so overlay blends only in that slice (no full-frame alloc).
            if did_crop:
                if track_source != "sleap" and track_xy_res is not None:
                    track_xy_res = (track_xy_res[0] + crop_x0, track_xy_res[1] + crop_y0)
                if track_source != "sleap" and pose_xy is not None and pose_xy.size > 0:
                    pose_xy = np.asarray(pose_xy, dtype=np.float64) + np.array(
                        [crop_x0, crop_y0]
                    )
                if in_range_xy_res is not None:
                    in_range_xy_res = (
                        in_range_xy_res[0] + crop_x0,
                        in_range_xy_res[1] + crop_y0,
                    )
                blob_mask = blob_mask_res
                blob_crop_rect = (
                    (crop_x0, crop_y0, crop_x1, crop_y1) if blob_mask_res is not None else None
                )
            else:
                blob_mask = blob_mask_res
                blob_crop_rect = None
            if track_xy_res is not None:
                track_xy = track_xy_res
                track_valid = track_valid_res
                if track_valid:
                    window._last_track_xy = track_xy
            else:
                # No result yet: keep last position for overlay but mark invalid.
                track_xy = getattr(window, "_last_track_xy", None)
                track_valid = False
            window._track_source_label.setText(overlay_state["source_label"])
            if (
                window._last_overlay_track_source is not None
                and track_source != window._last_overlay_track_source
            ):
                reset_sleap_node_jump_state(window)
            window._last_overlay_track_source = track_source

            # Minimal SLEAP device debug (once per session / device change).
            if (
                window._last_sleap_device_logged is None
                or (time.monotonic() - (window._last_sleap_log_time_s or 0.0)) > 2.0
            ):
                try:
                    sleap_label, sleap_tip = window._tracking_controller.get_sleap_status_label()
                    key = sleap_tip or sleap_label
                    if key and key != window._last_sleap_device_logged:
                        # Help->View error log: minimal one-line device info or load failure reason.
                        window._gui_log_error(f"SLEAP: {sleap_tip}")
                        window._last_sleap_device_logged = key
                        window._last_sleap_log_time_s = time.monotonic()
                except Exception:
                    # Best-effort debug; never break preview.
                    pass
            track_ms = (time.perf_counter() - _tp) * 1000.0
            _tp = time.perf_counter()
        else:
            track_ms = (time.perf_counter() - _tp) * 1000.0
            _tp = time.perf_counter()
            # show_track is False: no tracking overlay
            window._track_source_label.setText("—")
            window._last_overlay_track_source = None
        opacity = window._track_opacity.value() / 100.0
        if show_track or (roi_center is not None and roi_r > 0) or ram_polys_preview:
            ft = window._config.fallback_tracking
            node_max_jump_px = ft.node_max_jump_px
            node_jump_confirm = max(1, int(getattr(ft, "node_jump_confirm_frames", 2)))
            pose_node_valid = update_pose_last_and_valid(window, 
                pose_xy, node_max_jump_px, node_jump_confirm
            )
            # Combine confidence-based validity (from tracker) with jump-based validity
            if (
                pose_node_valid_from_res is not None
                and pose_xy is not None
                and pose_node_valid_from_res.shape == (pose_xy.shape[0],)
                and pose_node_valid is not None
                and pose_node_valid.shape == pose_node_valid_from_res.shape
            ):
                pose_node_valid = pose_node_valid & pose_node_valid_from_res
            img_display = draw_roi_and_tracking_overlay(
                img_display,
                roi_center,
                roi_r,
                track_xy,
                track_valid,
                opacity,
                overlay_info=window._trial_controller.get_overlay_info(),
                track_source=track_source,
                pose_xy=pose_xy,
                pose_scores=pose_scores,
                pose_edge_inds=pose_edge_inds,
                pose_node_names=pose_node_names,
                pose_node_valid=pose_node_valid,
                blob_mask=blob_mask,
                blob_crop_rect=blob_crop_rect,
                ram_polys=ram_polys_preview,
                ram_exit_xyr=ram_exit_preview,
                ram_all_holes_xyr=ram_all_holes_preview,
                ram_escape_arm_index=ram_escape_arm_preview,
            )
        else:
            pose_node_valid = None
        overlay_ms = (time.perf_counter() - _tp) * 1000.0
        _tp = time.perf_counter()
        tc = window._trial_controller
        exit_x_px, exit_y_px = tc.get_exit_position_px()
        exit_success_override = None
        if window._task_mode == "vast":
            exit_radius_px = window._config.arena.exit_radius_cm * window._config.arena.px_per_cm
            required_kp = max(1, int(getattr(window._config, "sleap_exit_min_keypoints", 2)))
            min_frac = max(
                0.0,
                min(
                    1.0,
                    float(
                        getattr(
                            window._config,
                            "fallback_exit_blob_overlap_pct",
                            15.0,
                        )
                    )
                    / 100.0,
                ),
            )
            exit_success_override = resolve_exit_success_override(
                pose_xy=pose_xy,
                pose_node_valid=pose_node_valid,
                pose_node_names=pose_node_names,
                blob_mask=blob_mask,
                blob_crop_rect=blob_crop_rect,
                track_xy=track_xy,
                track_source=track_source,
                exit_x_px=exit_x_px,
                exit_y_px=exit_y_px,
                exit_radius_px=exit_radius_px,
                required_keypoints=required_kp,
                min_blob_overlap_fraction=min_frac,
                allow_either_success=bool(
                    getattr(window._config, "track_exit_either_success", False)
                ),
            )
        elif window._task_mode == "ram":
            fallback_x = float(track_xy[0]) if track_xy is not None else float(roi_cx)
            fallback_y = float(track_xy[1]) if track_xy is not None else float(roi_cy)
            _, in_exit = tc.get_recording_frame_metrics(fallback_x, fallback_y)
            exit_success_override = bool(in_exit)
        tc.set_exit_success_override(exit_success_override)
        x_px = (
            float(window._last_track_xy[0])
            if window._last_track_xy is not None
            else (roi_cx or 0.0)
        )
        y_px = (
            float(window._last_track_xy[1])
            if window._last_track_xy is not None
            else (roi_cy or 0.0)
        )
        duty_pct = tc.get_duty_for_position(x_px, y_px)
        if window._arduino_stimulus is not None and window._arduino_stimulus.connected:
            window._arduino_stimulus.set_duty(duty_pct)
            for cmd in window._arduino_stimulus.read_pending_commands():
                if cmd == "T":
                    window._on_start_trial()
                    break
        # Per-trial recording: record entire trial slot (ITI + wait + trial) until SUCCESS/TIMEOUT
        output_dir = window._config.output_dir
        if tc.is_recording_trial() and output_dir:
            out_path = Path(output_dir)
            h5_name = (window._config.h5_filename or "trials.h5").strip() or "trials.h5"
            if Path(h5_name).name != h5_name:
                h5_name = Path(h5_name).name
            db_path = out_path / h5_name
            # Videos go in a subfolder named after the H5 file with _vids suffix (e.g. trials_vids)
            video_dir = out_path / f"{Path(h5_name).stem}_vids"
            x_px = 0.0
            y_px = 0.0
            if window._last_track_xy is not None:
                x_px, y_px = float(window._last_track_xy[0]), float(window._last_track_xy[1])
            elif roi_cx is not None and roi_cy is not None:
                x_px, y_px = float(roi_cx), float(roi_cy)
            exit_x, exit_y = tc.get_exit_position_px()
            duty_pct = tc.get_duty_for_position(x_px, y_px)
            dist_to_exit_px, in_exit = tc.get_recording_frame_metrics(x_px, y_px)
            region_code_str = tc.get_region_code_for_recording(x_px, y_px)
            trial_state_str = tc.get_trial_state_for_recording() or "iti"
            meta = tc.get_recording_metadata()
            if window._trial_recorder is None and meta is not None:
                animal_id, session_id, trial = meta
                seek_tf = 0
                virt_source: Optional[Path] = None
                if window._camera_source.currentText().startswith("Virtual"):
                    if (
                        hasattr(window, "_virtual_scrub_row_w")
                        and window._virtual_scrub_row_w.isVisible()
                    ):
                        seek_tf = int(window._virtual_scrub_slider.value())
                    if window._virtual_video_path is not None:
                        virt_source = Path(window._virtual_video_path)
                recording_ram_exit_arm_index: Optional[int] = None
                if isinstance(window._config, RadialArmControllerConfig):
                    sm_rec = window._trial_controller.get_state_machine()
                    if sm_rec is not None:
                        recording_ram_exit_arm_index = int(sm_rec.exit_arm_index)
                window._trial_recorder = TrialRecorder(
                    output_dir=video_dir,
                    db_path=db_path,
                    animal_id=animal_id,
                    session_id=session_id,
                    trial=trial,
                    config=window._config,
                    run_mode=window._config.run_mode or "continuous",
                    seek_to_frame=seek_tf,
                    virtual_source_video_path=virt_source,
                    recording_ram_exit_arm_index=recording_ram_exit_arm_index,
                )
                frame_shape = (img_raw.shape[0], img_raw.shape[1])
                if img_raw.ndim == 3:
                    frame_shape = img_raw.shape
                rec_fps = 30.0
                if window._camera_controller is not None:
                    v_fps = window._camera_controller.virtual_file_effective_fps(window._config)
                    if v_fps is not None:
                        rec_fps = float(v_fps)
                window._trial_recorder.start(frame_shape=frame_shape, fps=rec_fps)
                if virt_source is not None and window._camera_controller is not None:
                    fi, _ = window._camera_controller.get_last_frame_info()
                    window._record_frame_index = int(fi) if fi is not None else int(seek_tf)
                else:
                    window._record_frame_index = 0
            if window._trial_recorder is not None:
                try:
                    spot_xy_for_record: Optional[Tuple[float, float]] = None
                    in_range_xy_for_record: Optional[Tuple[float, float]] = None
                    centroid_xy_for_record: Optional[Tuple[float, float]] = None
                    if (
                        in_range_xy_res is not None
                        and len(in_range_xy_res) == 2
                        and np.isfinite(float(in_range_xy_res[0]))
                        and np.isfinite(float(in_range_xy_res[1]))
                    ):
                        in_range_xy_for_record = (
                            float(in_range_xy_res[0]),
                            float(in_range_xy_res[1]),
                        )
                    if track_valid and track_xy is not None:
                        if track_source == "sleap":
                            # Prefer SLEAP front-node mean for spot trajectory.
                            if (
                                pose_xy is not None
                                and pose_node_names is not None
                                and pose_xy.ndim == 2
                                and pose_xy.shape[1] == 2
                                and len(pose_node_names) >= pose_xy.shape[0]
                            ):
                                fore_names = {"nose", "neck", "foreL", "foreR"}
                                pts: list[tuple[float, float]] = []
                                for j in range(pose_xy.shape[0]):
                                    name = str(pose_node_names[j])
                                    if name not in fore_names:
                                        continue
                                    if (
                                        pose_node_valid is not None
                                        and j < pose_node_valid.shape[0]
                                        and not bool(pose_node_valid[j])
                                    ):
                                        continue
                                    xj = float(pose_xy[j, 0])
                                    yj = float(pose_xy[j, 1])
                                    if np.isfinite(xj) and np.isfinite(yj):
                                        pts.append((xj, yj))
                                if pts:
                                    xs, ys = zip(*pts)
                                    spot_xy_for_record = (
                                        float(np.mean(xs)),
                                        float(np.mean(ys)),
                                    )
                            # SLEAP centroid from all valid nodes.
                            if (
                                pose_xy is not None
                                and pose_xy.ndim == 2
                                and pose_xy.shape[1] == 2
                            ):
                                pts_all: list[tuple[float, float]] = []
                                for j in range(pose_xy.shape[0]):
                                    if (
                                        pose_node_valid is not None
                                        and j < pose_node_valid.shape[0]
                                        and not bool(pose_node_valid[j])
                                    ):
                                        continue
                                    xj = float(pose_xy[j, 0])
                                    yj = float(pose_xy[j, 1])
                                    if np.isfinite(xj) and np.isfinite(yj):
                                        pts_all.append((xj, yj))
                                if pts_all:
                                    xs_all, ys_all = zip(*pts_all)
                                    centroid_xy_for_record = (
                                        float(np.mean(xs_all)),
                                        float(np.mean(ys_all)),
                                    )
                            # Fallback to tracker point if front nodes aren't available this frame.
                            if spot_xy_for_record is None:
                                spot_xy_for_record = (float(track_xy[0]), float(track_xy[1]))

                    if (
                        window._camera_source.currentText().startswith("Virtual")
                        and window._camera_controller is not None
                    ):
                        fi, _ = window._camera_controller.get_last_frame_info()
                        rec_fi = int(fi) if fi is not None else int(window._record_frame_index)
                    else:
                        rec_fi = int(window._record_frame_index)
                        window._record_frame_index += 1
                    window._trial_recorder.write_frame(
                        image=img_raw,
                        frame_index=rec_fi,
                        x_px=x_px,
                        y_px=y_px,
                        dist_to_exit_px=dist_to_exit_px,
                        trial_state=trial_state_str,
                        region_code=region_code_str,
                        valid=track_valid,
                        duty_pct=duty_pct,
                        spot_xy=spot_xy_for_record,
                        in_range_xy=in_range_xy_for_record,
                        centroid_xy=centroid_xy_for_record,
                    )
                except Exception:
                    pass
        trial_ms = (time.perf_counter() - _tp) * 1000.0
        _tp = time.perf_counter()
        dev_ms = 0.0
        # Dev-only debug HUD overlay: draw simple text on the preview with per-frame diagnostics.
        if window._dev_mode and _cv2 is not None:
            _td0 = time.perf_counter()
            try:
                debug_lines = []
                debug_lines.append(
                    f"FPS {window._last_display_fps:.1f}  read {((t1 - t0) * 1000):.1f} ms"
                )
                debug_lines.append(
                    f"ph ms pre {preprocess_ms:.1f} disp {display_prep_ms:.1f} ram {ram_template_ms:.1f} "
                    f"trk {track_ms:.1f} ovl {overlay_ms:.1f} trial {trial_ms:.1f}"
                )
                debug_lines.append(f"track src {track_source}")
                y0 = 18
                for line in debug_lines:
                    # Outline in black, then inner text in white for readability
                    _cv2.putText(
                        img_display,
                        line,
                        (8, y0),
                        _cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (0, 0, 0),
                        3,
                        _cv2.LINE_AA,
                    )
                    _cv2.putText(
                        img_display,
                        line,
                        (8, y0),
                        _cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (255, 255, 255),
                        1,
                        _cv2.LINE_AA,
                    )
                    y0 += 16
            except Exception:
                # HUD is best-effort; never break preview if debug drawing fails
                pass
            dev_ms = (time.perf_counter() - _td0) * 1000.0
            _tp = time.perf_counter()

        _tqt0 = time.perf_counter()
        pix = frame_to_pixmap(img_display)
        if pix is not None:
            window._camera_label.setPixmap(
                pix.scaled(
                    window._camera_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        qt_ms = (time.perf_counter() - _tqt0) * 1000.0
        read_ms = (t1 - t0) * 1000
        process_ms = (time.perf_counter() - t1) * 1000
        window._last_frame_phase_ms = {
            "read": read_ms,
            "preprocess": preprocess_ms,
            "display_prep": display_prep_ms,
            "ram_template": ram_template_ms,
            "track": track_ms,
            "overlay": overlay_ms,
            "trial": trial_ms,
            "dev_hud": dev_ms,
            "qt_pixmap": qt_ms,
            "process_total": process_ms,
        }
        tt = "Preview frame rate.\n"
        tt += f"read {read_ms:.1f} ms | process total {process_ms:.1f} ms\n"
        tt += (
            f"preprocess {preprocess_ms:.1f} | display {display_prep_ms:.1f} | "
            f"ram_template {ram_template_ms:.1f} | track {track_ms:.1f}\n"
            f"overlay {overlay_ms:.1f} | trial {trial_ms:.1f} | dev {dev_ms:.1f} | qt {qt_ms:.1f}\n"
            f"backup={getattr(window._config, 'track_enable_backup', True)} "
            f"sleap={getattr(window._config, 'track_enable_sleap', True)}"
        )
        if window._camera_controller is not None:
            timing = window._camera_controller.virtual_file_timing_info(window._config)
            if timing is not None:
                nominal = timing.get("nominal_fps")
                effective = timing.get("effective_fps")
                override_s = timing.get("duration_override_s")
                nominal_s = f"{float(nominal):.3f}" if nominal is not None else "—"
                effective_s = f"{float(effective):.3f}" if effective is not None else "—"
                total_s = virtual_timing_frames_label(timing)
                override_s_txt = (
                    f"{float(override_s):.3f}s"
                    if (override_s is not None and float(override_s) > 0.0)
                    else "off"
                )
                tt += (
                    "\nvirtual timing: "
                    f"nominal_fps={nominal_s}, "
                    f"effective_fps={effective_s}, "
                    f"frames={total_s}, "
                    f"duration_override={override_s_txt}"
                )
        if hasattr(window, "_track_display_fps_label"):
            window._track_display_fps_label.setToolTip(tt)

def on_start_camera(window: MainWindow) -> None:
    if not HAS_CAMERA:
        return
    on_stop_camera(window)
    source = window._camera_source.currentText()
    # Reset virtual playback pause state; will be set again if user picks a video.
    window._virtual_video_path = None
    window._playback_hydration = None
    window._virtual_has_initial_frame = False
    window._virtual_cached_frame_raw = None
    window._virtual_cached_frame_index = None
    try:
        if window._camera_controller is not None:
            device_index = window._camera_device.value()
            video_path = None
            if source.startswith("Virtual"):
                video_path_str, _ = QFileDialog.getOpenFileName(
                    window,
                    "Select video file for virtual acquisition",
                    "",
                    "Video files (*.mp4 *.avi *.mkv *.mov);;All files (*)",
                )
                if not video_path_str:
                    return
                video_path = Path(video_path_str)
                window._virtual_video_path = video_path
                window._video_filename_label.setText(video_path.name)
                window._video_filename_label.setToolTip(str(video_path))
            else:
                window._video_filename_label.setText("—")
                window._video_filename_label.setToolTip("Current virtual video filename")
            window._camera_controller.open(source, device_index, video_path=video_path)
            if video_path is not None:
                window._playback_hydration = load_playback_hydration(
                    video_path,
                    task_mode=window._task_mode,
                    config=window._config,
                )
                if window._playback_hydration is not None:
                    window._session_id_edit.setText(window._playback_hydration.session_id)
            # Status message: keep simple for now; detailed backend info can
            # be added via CameraController hooks in the future.
            if video_path is not None and window._playback_hydration is not None:
                timing = (
                    window._camera_controller.virtual_file_timing_info(window._config)
                    if window._camera_controller is not None
                    else None
                )
                if timing is not None:
                    nominal = timing.get("nominal_fps")
                    effective = timing.get("effective_fps")
                    override_s = timing.get("duration_override_s")
                    nominal_s = f"{float(nominal):.3f}" if nominal is not None else "—"
                    effective_s = f"{float(effective):.3f}" if effective is not None else "—"
                    total_s = virtual_timing_frames_label(timing)
                    override_s_txt = (
                        f"{float(override_s):.3f}s"
                        if (override_s is not None and float(override_s) > 0.0)
                        else "off"
                    )
                    window.statusBar().showMessage(
                        f"{window._playback_hydration.status} | "
                        f"virtual timing: nominal {nominal_s} fps, "
                        f"effective {effective_s} fps, "
                        f"frames {total_s}, "
                        f"override {override_s_txt}"
                    )
                else:
                    window.statusBar().showMessage(window._playback_hydration.status)
            elif video_path is not None:
                timing = (
                    window._camera_controller.virtual_file_timing_info(window._config)
                    if window._camera_controller is not None
                    else None
                )
                if timing is not None:
                    nominal = timing.get("nominal_fps")
                    effective = timing.get("effective_fps")
                    override_s = timing.get("duration_override_s")
                    nominal_s = f"{float(nominal):.3f}" if nominal is not None else "—"
                    effective_s = f"{float(effective):.3f}" if effective is not None else "—"
                    total_s = virtual_timing_frames_label(timing)
                    override_s_txt = (
                        f"{float(override_s):.3f}s"
                        if (override_s is not None and float(override_s) > 0.0)
                        else "off"
                    )
                    window.statusBar().showMessage(
                        f"Virtual video started ({source}): {video_path.name} | "
                        f"timing nominal {nominal_s} fps, effective {effective_s} fps, "
                        f"frames {total_s}, override {override_s_txt}"
                    )
                else:
                    window.statusBar().showMessage(
                        f"Virtual video started ({source}): {video_path.name}"
                    )
            else:
                window.statusBar().showMessage(f"Camera {device_index} started ({source}).")
        window._camera_timer = QTimer(window)
        window._camera_timer.setTimerType(
            Qt.TimerType.PreciseTimer
        )  # better accuracy on Windows for 30 FPS
        window._camera_timer.timeout.connect(window._on_camera_tick)
        tick_ms = (
            window._camera_controller.preview_timer_interval_ms(window._config)
            if window._camera_controller is not None
            else 33
        )
        window._camera_timer.start(tick_ms)
        window._camera_start_btn.setEnabled(False)
        window._camera_stop_btn.setEnabled(True)
        # Start tracking controller (async or sync)
        if window._tracking_controller is not None:
            window._tracking_controller.start(async_enabled=window._config.track_async)
        apply_status_and_buttons(window)
    except Exception as e:
        window.statusBar().showMessage(f"Camera failed: {e}")
        if window._camera_controller is not None:
            window._camera_controller.close()

def on_stop_camera(window: MainWindow) -> None:
    if window._arduino_stimulus is not None and window._arduino_stimulus.connected:
        window._arduino_stimulus.set_duty(0)
    # Stop tracking controller
    if window._tracking_controller is not None:
        window._tracking_controller.stop()
    if window._camera_timer is not None:
        window._camera_timer.stop()
        window._camera_timer = None
    if window._camera_controller is not None:
        window._camera_controller.close()
    window._camera_start_btn.setEnabled(True)
    window._camera_stop_btn.setEnabled(False)
    window._camera_label.clear()
    window._camera_label.setText("Click Start camera")
    window._last_eyedropper_frame_bgr = None
    if hasattr(window, "_intensity_hover_label") and window._intensity_hover_label is not None:
        window._intensity_hover_label.setText("—")
    window.statusBar().showMessage("Camera stopped.")
    window._virtual_video_path = None
    window._playback_hydration = None
    window._video_filename_label.setText("—")
    window._video_filename_label.setToolTip("Current virtual video filename")
    window._virtual_has_initial_frame = False
    window._virtual_cached_frame_raw = None
    window._virtual_cached_frame_index = None
    apply_status_and_buttons(window)

def is_video_available(window: MainWindow) -> bool:
    """True if camera is running and we can record video (required to run trials)."""
    return bool(HAS_CAMERA and window._camera_timer is not None and window._camera_timer.isActive())

def virtual_timing_frames_label(timing: Dict[str, Any]) -> str:
    """Frame count for virtual HUD: pacing window / file total when they differ."""
    total = timing.get("total_frames")
    tf = timing.get("total_frames_for_effective_fps")
    override_s = timing.get("duration_override_s")
    if total is None:
        return "—"
    t_int = int(total)
    if override_s is None or float(override_s) <= 0.0 or tf is None:
        return str(t_int)
    tf_int = int(tf)
    if tf_int != t_int:
        return f"{tf_int}/{t_int}"
    return str(t_int)
