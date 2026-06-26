"""
Per-trial runtime for the shared maze pipeline.

This module executes one trial against the shared result-database contract:
1. Read persisted trial settings from the results DB.
2. Load SLEAP or controller-written tracking sources.
3. Apply shared trace processing.
4. Compute shared ambulation metrics plus task-specific overlays.
5. Write summaries, QC products, and mistrial metadata back to the results DB.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

import numpy as np

from maze.controller.acquisition.region_code import (
    arena_config_from_trial_settings,
    compute_trace_region_codes,
)
from maze.controller.acquisition.vast.config import ExitAngleConfig

from ..core.anatomy import SPOT_NODE_NAMES
from ..core.tasks import ARENA_TYPE_RADIAL_ARM
from ..core.trial_settings import TrialSettings
from .defaults import (
    DEFAULT_FPS,
    EXIT_ZONE_RADIUS_CM,
    CENTER_ZONE_RADIUS_FRACTION,
    CENTER_ZONE_RADIUS_CM,
    AMBIULATION_POINT_NAMES,
    IN_RANGE_POINT_NAME,
    HYBRID_POINT_NAME,
)
from .paths import OUTPUT_H5
from .io.file_discovery import TrialManifest, load_treatment_labels
from .io.sleap_loader import (
    load_sleap_file,
    apply_jump_filter,
    trace_data_from_realtime_xy,
    trace_data_from_legacy_xy,
    TraceData,
)
from .tracking.trace_processing import (
    process_trace_data,
    filter_frames_no_animal,
    TraceProcessingParams,
)
from .metrics.ambulation import calculate_ambulation_metrics
from .metrics.exit_metrics import (
    build_xy_table_with_exit,
)
from .metrics.task_metrics import calculate_task_metrics, summary_fields_for_task
from .trial_quality import (
    REASON_NO_EXIT_XY,
    REASON_NO_TRACKING,
    REASON_PROCESSING_ERROR,
)
from .db import (
    TrialKey,
    complete_trial_timing,
    compute_seek_run_rows,
    read_arena_type,
    read_radial_arm_trial_settings,
    read_spot_frame_index_column,
    read_trial_settings,
    persist_effective_analysis_params,
    read_feedback_series,
    write_mistrial_reason,
    write_video_meta,
    write_analysis_duration,
    write_xy_table,
    write_movement_bouts,
    write_node_summary_by_state,
    write_feedback_error_summary,
    write_config_params,
    write_primary_trajectory,
    write_animal_notes_attr,
    write_trial_attrs,
    read_animal_label,
    TrialTiming,
)
from .db.trial_settings_io import radial_arm_exit_hole_from_geometry_payload
from .persist_pose import persist_pose_from_sidecar
from .pose_status import (
    overwrite_pose_to_policy,
    read_anatomical_for_trial,
    status_for_persist_result,
    write_pose_status_attrs,
)

if TYPE_CHECKING:
    from maze.controller.acquisition.shared_config import (
        AnalysisTraceQualityConfig,
        AnalysisTrajectoryConfig,
    )

log = logging.getLogger(__name__)


def _ram_exit_arm_index_for_pipeline(
    radial_arm_payload: dict[str, Any],
    settings: TrialSettings,
) -> int:
    """0-based RAM exit arm for metrics/QC: prefer per-trial attrs, then task attrs, then exit_number."""
    trial_attrs = radial_arm_payload.get("trial_attrs") or {}
    task_attrs = radial_arm_payload.get("task_attrs") or {}

    def _parse_exit_arm(raw: Any) -> Optional[int]:
        if raw is None:
            return None
        try:
            v = int(raw)
            if v < 0:
                return None
            return v
        except (TypeError, ValueError):
            return None

    v = _parse_exit_arm(trial_attrs.get("exit_arm_index"))
    if v is not None:
        return max(0, min(7, v))
    v = _parse_exit_arm(task_attrs.get("exit_arm_index"))
    if v is not None:
        return max(0, min(7, v))
    if settings.exit_number is not None:
        try:
            en = int(settings.exit_number)
            if en > 0:
                return max(0, min(7, en - 1))
        except (TypeError, ValueError):
            pass
    return 0


def _animal_notes_from_treatment_csv(manifest: TrialManifest) -> str:
    """Resolve notes from ``inputs/treatment_labels.csv`` using animal_id then inferred_id."""
    labels = load_treatment_labels()
    for k in (manifest.animal_id, manifest.inferred_id or ""):
        if k and k.strip() and k in labels:
            return labels[k].notes or ""
    return ""


def _animal_notes(manifest: TrialManifest, db_path: Path) -> str:
    """Resolve animal notes from DB attrs first, then fallback CSV labels."""
    db_labels = read_animal_label(db_path, manifest.animal_id)
    notes = (db_labels.get("notes", "") or "").strip()
    if notes:
        return notes
    return _animal_notes_from_treatment_csv(manifest)


def _merge_trace_data(
    trace_data_sleap: Optional[TraceData],
    trace_data_inrange: Optional[TraceData],
    inrange_point_name: str,
) -> Optional[TraceData]:
    """
    Merge SLEAP and in-range TraceData into one. When both present, in-range is aligned
    to SLEAP n_frames (pad with NaN or truncate). When only one present, return it.
    """
    if trace_data_sleap is None and trace_data_inrange is None:
        return None
    if trace_data_sleap is None:
        return trace_data_inrange
    if trace_data_inrange is None:
        return trace_data_sleap
    n_frames = trace_data_sleap.n_frames
    inrange_traces = trace_data_inrange.traces.get(inrange_point_name)
    if not inrange_traces:
        return trace_data_sleap
    x = np.asarray(inrange_traces["x"], dtype=np.float64)
    y = np.asarray(inrange_traces["y"], dtype=np.float64)
    score = np.asarray(inrange_traces["score"], dtype=np.float64)
    visible = np.asarray(inrange_traces["visible"], dtype=np.float64)
    nr = len(x)
    if nr < n_frames:
        x = np.concatenate([x, np.full(n_frames - nr, np.nan)])
        y = np.concatenate([y, np.full(n_frames - nr, np.nan)])
        score = np.concatenate([score, np.zeros(n_frames - nr, dtype=np.float64)])
        visible = np.concatenate([visible, np.zeros(n_frames - nr, dtype=np.float64)])
    elif nr > n_frames:
        x = x[:n_frames]
        y = y[:n_frames]
        score = score[:n_frames]
        visible = visible[:n_frames]
    combined_traces = dict(trace_data_sleap.traces)
    combined_traces[inrange_point_name] = {"x": x, "y": y, "score": score, "visible": visible}
    combined_node_names = list(trace_data_sleap.node_names) + [inrange_point_name]
    return TraceData(
        traces=combined_traces,
        node_names=combined_node_names,
        n_frames=n_frames,
        fps=trace_data_sleap.fps,
        source_path=trace_data_sleap.source_path,
    )


def process_trial(
    manifest: TrialManifest,
    db_path: Optional[Path] = None,
    generate_qc: bool = True,
    quiet: bool = False,
    analysis_profile: Optional[
        tuple["AnalysisTrajectoryConfig", "AnalysisTraceQualityConfig"]
    ] = None,
    overwrite_pose: bool = False,
) -> bool:
    """
    Process a single trial through the complete pipeline.

    Args:
        manifest: Trial manifest with file paths
        db_path: Path to output database (uses config default if None)
        generate_qc: Whether to generate QC visualizations
        quiet: If True, suppress per-trial status messages (for batch mode)
        analysis_profile: When set, merge trajectory + trace-quality from the GUI profile
            into settings before processing; effective values are persisted on success.

    Returns:
        True if processing succeeded, False otherwise
    """
    db_path = db_path or OUTPUT_H5

    # Helper for conditional printing (tqdm.write so bar stays at bottom when run in batch)
    def log(msg: str) -> None:
        if not quiet:
            from tqdm import tqdm

            tqdm.write(msg)

    # Create trial key (path = /animal_id/session/trial; phase derived from session)
    key = TrialKey.from_manifest(manifest)
    write_animal_notes_attr(db_path, key.animal_id, _animal_notes(manifest, db_path))

    log(f"Processing {key.path()}...")

    try:
        # Step 1: Read trial settings from output database (written by init_db)
        settings, h5_fps, timing = read_trial_settings(db_path, key)
        if analysis_profile is not None:
            from maze.pipeline.analysis_profile_merge import (
                merge_analysis_profile_into_trial_settings,
            )

            traj_p, tq_p = analysis_profile
            settings = merge_analysis_profile_into_trial_settings(settings, traj_p, tq_p)
        if h5_fps is None:
            h5_fps = DEFAULT_FPS
        timing = complete_trial_timing(db_path, key, timing)

        if manifest.sleap_path and manifest.sleap_path.exists():
            persist_result = persist_pose_from_sidecar(
                db_path,
                key,
                manifest.sleap_path,
                overwrite_pose=overwrite_pose,
                fps=h5_fps,
            )
            anatomical = read_anatomical_for_trial(db_path, key)
            pose_status = status_for_persist_result(
                persist_result,
                anatomical,
                sleap_path=manifest.sleap_path,
                overwrite_pose=overwrite_pose,
            )
            write_pose_status_attrs(
                db_path,
                key,
                status=pose_status,
                policy=overwrite_pose_to_policy(overwrite_pose),
            )
            log(f"{key.path()} — {pose_status}")

        # Step 2: Load tracking data (SLEAP + in-range when available; merge into one TraceData)
        trace_data_sleap = None
        if manifest.sleap_path and manifest.sleap_path.exists():
            trace_data_sleap = load_sleap_file(manifest.sleap_path)
            if trace_data_sleap is not None:
                trace_data_sleap = apply_jump_filter(
                    trace_data_sleap,
                    px_per_cm=settings.px_per_cm,
                    max_jump_cm=settings.max_movement_per_frame_cm,
                    lookahead_frames=settings.jump_filter_lookahead_frames,
                )
            else:
                log("  Warning: Failed to load SLEAP data")

        trace_data_realtime_spot = None
        trace_data_realtime_centroid = None
        trace_data_inrange = None
        # In-range: from output DB (controller-written) or legacy input H5
        if trace_data_sleap is None:
            trace_data_realtime_spot = trace_data_from_realtime_xy(
                db_path,
                key,
                point_name="spot",
                fps=h5_fps or DEFAULT_FPS,
            )
            trace_data_realtime_centroid = trace_data_from_realtime_xy(
                db_path,
                key,
                point_name="centroid",
                fps=h5_fps or DEFAULT_FPS,
            )
        trace_data_inrange = trace_data_from_realtime_xy(
            db_path,
            key,
            point_name=IN_RANGE_POINT_NAME,
            fps=h5_fps or DEFAULT_FPS,
        )
        if (
            trace_data_inrange is None
            and manifest.input_h5_path
            and manifest.input_h5_path.exists()
        ):
            trace_data_inrange = trace_data_from_legacy_xy(
                manifest.input_h5_path,
                manifest.animal_id,
                manifest.session,
                manifest.trial,
                fps=h5_fps or DEFAULT_FPS,
            )

        base_trace = trace_data_sleap if trace_data_sleap is not None else trace_data_realtime_spot
        trace_data = _merge_trace_data(base_trace, trace_data_inrange, IN_RANGE_POINT_NAME)
        if trace_data is not None and trace_data_realtime_centroid is not None:
            cnode = trace_data_realtime_centroid.traces.get("centroid")
            if cnode is not None:
                trace_data.traces["centroid"] = cnode
                if "centroid" not in trace_data.node_names:
                    trace_data.node_names.append("centroid")
        if trace_data is None:
            log("  No tracking data (SLEAP and in-range unavailable); skipping full write.")
            write_mistrial_reason(db_path, key, REASON_NO_TRACKING)
            return False

        ok = _process_with_sleap(
            key=key,
            settings=settings,
            trace_data=trace_data,
            db_path=db_path,
            generate_qc=generate_qc,
            fps_override=h5_fps,
            timing=timing,
        )
        if not ok:
            log("  Incomplete processing (no analysis window or invalid arena); marking as failed.")
            return False

        # Write config params for reproducibility
        write_config_params(db_path, key)

        log(f"  Completed: {key.path()}")
        return True

    except Exception as e:
        # Always print errors, even in quiet mode (use tqdm.write so bar stays at bottom in batch)
        import traceback
        from tqdm import tqdm

        tqdm.write(f"  Error processing {key.path()}: {e}")
        tqdm.write(traceback.format_exc())
        # Record as mistrial so it appears in mistrial summary
        reason = f"{REASON_PROCESSING_ERROR}: {type(e).__name__}"
        write_mistrial_reason(db_path, key, reason)
        return False


def _process_with_sleap(
    key: TrialKey,
    settings: TrialSettings,
    trace_data: TraceData,
    db_path: Path,
    generate_qc: bool = True,
    fps_override: Optional[float] = None,
    timing: Optional[TrialTiming] = None,
) -> bool:
    """
    Process trial with SLEAP tracking data.

    Analysis uses only frames from the run row onward (post-ITI within the seek window).
    Returns True if full pipeline ran and data was written; False on early exit
    (e.g. no analysis frames or invalid arena), so the caller can mark the trial as failed.
    """
    if timing is None:
        timing = TrialTiming(seek_to_frame=0, run_start_frame=0, use_absolute_frame_index=False)
    # FPS: h5_fps (from DB, from input H5 timer0) when available, else SLEAP trace, else config default. Not changed by pipeline.
    if fps_override and fps_override > 0:
        fps = fps_override
    elif trace_data.fps > 0:
        fps = trace_data.fps
    else:
        fps = DEFAULT_FPS
    n_frames = trace_data.n_frames

    fi_spot = read_spot_frame_index_column(db_path, key)
    seek_row, run_row = compute_seek_run_rows(n_frames, fi_spot, timing)
    start_frame = run_row
    if start_frame >= n_frames:
        return False
    n_analysis = n_frames - start_frame

    # Write video metadata (full recording)
    duration_s = n_frames / fps
    write_video_meta(db_path, key, fps=fps, n_frames=n_frames, duration_s=duration_s)
    # Analysis-window duration (excludes ITI); CSV export prefers this over duration_s for "trial duration"
    analysis_duration_s = n_analysis / fps
    write_analysis_duration(db_path, key, analysis_duration_s)

    # Frame-level confidence: keep only frames with enough confident nodes (and optional mean conf).
    # Result is applied to metrics so low-confidence frames are excluded from ambulation/exit.
    valid_frames_full = filter_frames_no_animal(
        trace_data.traces,
        n_frames,
        min_confident_nodes=settings.min_confident_nodes_per_frame,
        min_confidence=settings.min_node_confidence_threshold,
        min_valid_run_length=settings.min_valid_frame_run_length,
        min_mean_confidence=settings.min_mean_confidence_per_frame,
    )
    valid_frames_analysis = valid_frames_full[start_frame:]  # length n_analysis
    # Process traces (interpolation, smoothing) full length
    params = TraceProcessingParams(
        interpolate_nans=settings.trace_interpolate_nans,
        max_gap_frames=settings.trace_max_gap_frames,
        interpolate_low_conf=settings.trace_interpolate_low_conf,
        confidence_threshold=settings.trace_confidence_threshold,
        apply_smoothing=settings.trace_apply_smoothing,
        smoothing_window=settings.trace_smoothing_window,
    )
    processed_traces = process_trace_data(
        trace_data.traces,
        trace_data.node_names,
        params,
    )

    arena_type = read_arena_type(db_path)

    # No exit in H5 -> use arena center as a fallback target. VAST still records
    # an explicit mistrial for experimental trials, while RAM can legitimately
    # rely on mirrored shared attrs or this center fallback until richer metrics land.
    exit_pos = settings.exit_pos
    if exit_pos is None:
        if settings.arena_radius_px <= 0:
            return False
        if key.phase == "experimental" and arena_type != ARENA_TYPE_RADIAL_ARM:
            write_mistrial_reason(db_path, key, REASON_NO_EXIT_XY)
        exit_pos = (settings.arena_center_x_px, settings.arena_center_y_px)
        exit_zone_radius_cm = CENTER_ZONE_RADIUS_FRACTION * settings.arena_radius_cm
    else:
        exit_zone_radius_cm = settings.exit_radius_cm or EXIT_ZONE_RADIUS_CM

    # Center zone (for center entries): 70% of arena radius from H5, else fallback
    if settings.arena_radius_px > 0:
        center_zone_radius_cm = CENTER_ZONE_RADIUS_FRACTION * settings.arena_radius_cm
    else:
        center_zone_radius_cm = CENTER_ZONE_RADIUS_CM
    spot_xy_full = _calculate_spot_xy(processed_traces, n_frames)
    centroid_xy_full = _calculate_centroid_xy(processed_traces, n_frames)
    inrange_xy_full = _get_inrange_xy(processed_traces, n_frames)

    # Valid masks for full-length traces (before analysis-window split)
    spot_valid_full = ~np.any(np.isnan(spot_xy_full), axis=1)
    inrange_valid_full = ~np.any(np.isnan(inrange_xy_full), axis=1)
    if settings.filter_frames_no_animal:
        spot_valid_full = spot_valid_full & valid_frames_full
        inrange_valid_full = inrange_valid_full & valid_frames_full

    # Build hybrid trajectory: SLEAP spot, but replace long SLEAP gaps with in-range when available.
    # First compute max gap on analysis window (matching existing primary selection logic).
    spot_xy = spot_xy_full[start_frame:]
    inrange_xy = inrange_xy_full[start_frame:]

    # Hybrid valid mask and gap logic over the analysis window
    spot_valid_analysis = spot_valid_full[start_frame:]
    max_gap_spot = _max_gap_in_trace(spot_xy, spot_valid_analysis)

    # Per-frame replacement mask: frames inside any invalid run longer than trace_max_gap_frames.
    replace_with_inrange_full = np.zeros(n_frames, dtype=bool)
    invalid_spot = ~np.asarray(spot_valid_full, dtype=bool)
    if np.any(invalid_spot):
        changes = np.diff(np.concatenate([[False], invalid_spot, [False]]).astype(np.int8))
        starts = np.where(changes == 1)[0]
        ends = np.where(changes == -1)[0]
        lengths = ends - starts
        for s, e, L in zip(starts, ends, lengths):
            if L > settings.trace_max_gap_frames:
                replace_with_inrange_full[s:e] = True

    use_inrange_here_full = replace_with_inrange_full & inrange_valid_full

    hybrid_xy_full = spot_xy_full.copy()
    if np.any(use_inrange_here_full):
        hybrid_xy_full[use_inrange_here_full] = inrange_xy_full[use_inrange_here_full]

    # Expose hybrid trace as another node in processed_traces so downstream code can use it.
    processed_traces[HYBRID_POINT_NAME] = {
        "x": hybrid_xy_full[:, 0],
        "y": hybrid_xy_full[:, 1],
    }
    hybrid_valid_full = ~np.any(np.isnan(hybrid_xy_full), axis=1)
    if settings.filter_frames_no_animal:
        hybrid_valid_full = hybrid_valid_full & valid_frames_full
    hybrid_xy_run = hybrid_xy_full[start_frame:]
    hybrid_valid_run = hybrid_valid_full[start_frame:]
    hybrid_xy_iti = hybrid_xy_full[seek_row:run_row]
    hybrid_valid_iti = hybrid_valid_full[seek_row:run_row]
    radial_arm_payload: dict[str, Any] = {}
    task_context: dict[str, Any] | None = None
    if arena_type == ARENA_TYPE_RADIAL_ARM:
        radial_arm_payload = read_radial_arm_trial_settings(db_path, key)
        exit_arm_resolved = _ram_exit_arm_index_for_pipeline(radial_arm_payload, settings)
        task_context = {
            "geometry_payload": radial_arm_payload.get("geometry_payload", {}),
            "exit_arm_index": exit_arm_resolved,
            "rewarded_arm_index": radial_arm_payload.get("task_attrs", {}).get(
                "rewarded_arm_index",
                radial_arm_payload.get("trial_attrs", {}).get("rewarded_arm_index", 0),
            ),
        }

    arena_cfg_region = arena_config_from_trial_settings(settings)
    exit_angles_region = ExitAngleConfig()
    assigned_vast_region = max(0, int(settings.exit_number or 1) - 1)
    gp_ram_region: dict = {}
    exit_arm_region = 0
    if arena_type == ARENA_TYPE_RADIAL_ARM and task_context:
        gp_ram_region = dict(task_context.get("geometry_payload") or {})
        exit_arm_region = int(task_context.get("exit_arm_index", 0) or 0)
        exit_arm_region = max(0, min(7, exit_arm_region))

    for point_name in AMBIULATION_POINT_NAMES:
        if point_name == "spot":
            xy_full = spot_xy_full
        elif point_name == "centroid":
            xy_full = centroid_xy_full
        elif point_name == IN_RANGE_POINT_NAME:
            xy_full = inrange_xy_full
        elif point_name == HYBRID_POINT_NAME:
            xy_full = hybrid_xy_full
        else:
            xy_full = centroid_xy_full

        # Full valid mask: finite coords and (optionally) frame-level confidence filter.
        valid_full = ~np.any(np.isnan(xy_full), axis=1)
        if settings.filter_frames_no_animal:
            valid_full = valid_full & valid_frames_full

        # ITI band: between seek_row and run_row; run band: from run_row onward.
        xy_iti = xy_full[seek_row:run_row]
        xy_run = xy_full[start_frame:]
        valid_iti = valid_full[seek_row:run_row]
        valid_run = valid_full[start_frame:]

        amb_iti = None
        if run_row > seek_row and xy_iti.shape[0] > 0:
            amb_iti = calculate_ambulation_metrics(
                xy=xy_iti,
                valid=valid_iti,
                px_per_cm=settings.px_per_cm,
                fps=fps,
                start_threshold_m=settings.movement_start_threshold_m_per_frame,
                stop_threshold_m=settings.movement_stop_threshold_m_per_frame,
                speed_median_window_frames=settings.movement_speed_median_window_frames,
                entry_debounce_frames=settings.movement_entry_debounce_frames,
                exit_debounce_frames=settings.movement_exit_debounce_frames,
                min_bout_duration_frames=settings.min_movement_bout_duration_frames,
                inter_bout_interval_frames=settings.movement_inter_bout_interval_frames,
            )

        # Run-band metrics (matches existing analysis semantics).
        amb_run = calculate_ambulation_metrics(
            xy=xy_run,
            valid=valid_run,
            px_per_cm=settings.px_per_cm,
            fps=fps,
            start_threshold_m=settings.movement_start_threshold_m_per_frame,
            stop_threshold_m=settings.movement_stop_threshold_m_per_frame,
            speed_median_window_frames=settings.movement_speed_median_window_frames,
            entry_debounce_frames=settings.movement_entry_debounce_frames,
            exit_debounce_frames=settings.movement_exit_debounce_frames,
            min_bout_duration_frames=settings.min_movement_bout_duration_frames,
            inter_bout_interval_frames=settings.movement_inter_bout_interval_frames,
        )
        arena_center = (settings.arena_center_x_px, settings.arena_center_y_px)
        task_xy_run = hybrid_xy_run if arena_type == ARENA_TYPE_RADIAL_ARM else xy_run
        task_valid_run = hybrid_valid_run if arena_type == ARENA_TYPE_RADIAL_ARM else valid_run
        task_run = calculate_task_metrics(
            arena_type=arena_type,
            xy=task_xy_run,
            valid=task_valid_run,
            exit_pos=exit_pos,
            arena_center_pos=arena_center,
            px_per_cm=settings.px_per_cm,
            fps=fps,
            exit_zone_radius_cm=exit_zone_radius_cm,
            center_zone_radius_cm=center_zone_radius_cm,
            task_context=task_context,
        )
        exit_run = task_run.exit_metrics
        center_run = task_run.center_metrics

        # Movement bouts for run band (for metrics); expand to full-video mask for xy table.
        is_moving_run = np.zeros(n_analysis, dtype=bool)
        for bout in amb_run.movement_bouts:
            start = bout["start_frame"]
            end = min(bout["end_frame"] + 1, n_analysis)
            is_moving_run[start:end] = True
        is_moving_full = np.zeros(n_frames, dtype=bool)
        is_moving_full[start_frame : start_frame + n_analysis] = is_moving_run

        # Build xy table over full video (frame_index 0 .. n_frames-1).
        _fi_write = None
        if fi_spot is not None and len(fi_spot) == n_frames:
            _fi_write = fi_spot
        rc_list = compute_trace_region_codes(
            xy_full,
            arena_type=arena_type,
            geometry_payload=gp_ram_region if arena_type == ARENA_TYPE_RADIAL_ARM else None,
            exit_arm_index=exit_arm_region,
            arena_config=arena_cfg_region,
            exit_angles=exit_angles_region,
            assigned_exit_index=assigned_vast_region,
        )
        xy_table = build_xy_table_with_exit(
            xy=xy_full,
            valid=valid_full,
            exit_pos=exit_pos,
            px_per_cm=settings.px_per_cm,
            fps=fps,
            exit_zone_radius_cm=exit_zone_radius_cm,
            is_moving=is_moving_full,
            seek_row=seek_row,
            run_row=run_row,
            frame_indices=_fi_write,
            region_codes=rc_list,
        )

        write_xy_table(db_path, key, point_name, xy_table, fps)
        combined_bouts: list[dict[str, Any]] = []
        if amb_iti is not None:
            for b in amb_iti.movement_bouts:
                nb = dict(b)
                nb["trial_state"] = "iti_wait"
                nb["start_frame"] = seek_row + int(b["start_frame"])
                nb["end_frame"] = seek_row + int(b["end_frame"])
                combined_bouts.append(nb)
        for b in amb_run.movement_bouts:
            nb = dict(b)
            nb["trial_state"] = "run"
            nb["start_frame"] = start_frame + int(b["start_frame"])
            nb["end_frame"] = start_frame + int(b["end_frame"])
            combined_bouts.append(nb)
        combined_bouts.sort(key=lambda x: int(x["start_frame"]))
        write_movement_bouts(db_path, key, point_name, combined_bouts, analysis_start_frame=0)

        run_summary = {
            "total_distance_m": amb_run.total_distance_m,
            "mean_speed_mps": amb_run.mean_speed_mps,
            "max_speed_mps": amb_run.max_speed_mps,
            "time_moving_s": amb_run.time_moving_s,
            "time_immobile_s": amb_run.time_immobile_s,
            "n_movement_bouts": amb_run.n_movement_bouts,
            **summary_fields_for_task(
                arena_type=arena_type,
                exit_metrics=exit_run,
                center_metrics=center_run,
            ),
        }

        # Optional iti_wait-band metrics (seek..run slice only; skip when empty).
        band_summaries: list[dict[str, Any]] = []
        if amb_iti is not None:
            task_xy_iti = hybrid_xy_iti if arena_type == ARENA_TYPE_RADIAL_ARM else xy_iti
            task_valid_iti = hybrid_valid_iti if arena_type == ARENA_TYPE_RADIAL_ARM else valid_iti
            task_iti = calculate_task_metrics(
                arena_type=arena_type,
                xy=task_xy_iti,
                valid=task_valid_iti,
                exit_pos=exit_pos,
                arena_center_pos=arena_center,
                px_per_cm=settings.px_per_cm,
                fps=fps,
                exit_zone_radius_cm=exit_zone_radius_cm,
                center_zone_radius_cm=center_zone_radius_cm,
                task_context=task_context,
            )
            band_summaries.append(
                {
                    "trial_state": "iti_wait",
                    "total_distance_m": amb_iti.total_distance_m,
                    "mean_speed_mps": amb_iti.mean_speed_mps,
                    "max_speed_mps": amb_iti.max_speed_mps,
                    "time_moving_s": amb_iti.time_moving_s,
                    "time_immobile_s": amb_iti.time_immobile_s,
                    "n_movement_bouts": amb_iti.n_movement_bouts,
                    **summary_fields_for_task(
                        arena_type=arena_type,
                        exit_metrics=task_iti.exit_metrics,
                        center_metrics=task_iti.center_metrics,
                    ),
                }
            )

        band_summaries.append(
            {
                "trial_state": "run",
                **run_summary,
            }
        )
        write_node_summary_by_state(db_path, key, point_name, band_summaries)
        write_trial_attrs(db_path, key, task_run.extra_trial_attrs)

    # Primary trajectory for export: prefer hybrid; record when in-range contributed.
    spot_valid = ~np.any(np.isnan(spot_xy), axis=1)
    if settings.filter_frames_no_animal:
        spot_valid = spot_valid & valid_frames_analysis
    inrange_valid = ~np.any(np.isnan(inrange_xy), axis=1)
    if settings.filter_frames_no_animal:
        inrange_valid = inrange_valid & valid_frames_analysis
    use_inrange_primary = max_gap_spot > settings.trace_max_gap_frames and np.any(inrange_valid)
    primary_trajectory = HYBRID_POINT_NAME
    write_primary_trajectory(db_path, key, primary_trajectory)

    # Feedback error (incongruent feedback) from W/M vs distance-to-exit
    # Always write summary (0, 0.0 when feedback missing) so export and attrs exist
    n_incongruent_bouts = 0
    incongruent_duration_s = 0.0
    feedback_series = read_feedback_series(db_path, key)
    if feedback_series is not None:
        n_fb = len(feedback_series[0])
        # Trim to n_analysis to fix off-by-one (H5 analysis window can be 1 frame longer than video/SLEAP)
        n_use = min(n_fb, n_analysis)
        if n_use > 0:
            m_fb = np.asarray(feedback_series[1][:n_use], dtype=np.float64)
            exit_x, exit_y = exit_pos
            xy_use = spot_xy[:n_use]
            dx = xy_use[:, 0] - exit_x
            dy = xy_use[:, 1] - exit_y
            distance_to_exit_cm = np.sqrt(dx**2 + dy**2) / settings.px_per_cm
            delta_dist = np.diff(distance_to_exit_cm)
            delta_fb = np.diff(m_fb)
            incongruent = ((delta_dist > 0) & (delta_fb > 0)) | ((delta_dist < 0) & (delta_fb < 0))
            incongruent_padded = np.concatenate([[False], incongruent, [False]])
            n_incongruent_bouts = int(np.sum(np.diff(incongruent_padded.astype(np.int8)) == 1))
            incongruent_duration_s = float(np.sum(incongruent)) / fps if fps > 0 else 0.0
    write_feedback_error_summary(db_path, key, n_incongruent_bouts, incongruent_duration_s)

    if generate_qc:
        try:
            from .viz.qc_images import generate_trial_qc_images

            # Heatmap from all nodes (split into iti_wait vs run bands); trajectory from hybrid point.
            xy_all_nodes_iti: list[tuple[np.ndarray, np.ndarray]] = []
            xy_all_nodes_run: list[tuple[np.ndarray, np.ndarray]] = []
            heatmap_node_names: list[str] = []
            for node_name in trace_data.node_names:
                if node_name == IN_RANGE_POINT_NAME or node_name not in processed_traces:
                    continue
                heatmap_node_names.append(node_name)
                node = processed_traces[node_name]
                x_full = node["x"]
                y_full = node["y"]
                xy_full = np.column_stack([x_full, y_full])
                valid_full_node = ~np.any(np.isnan(xy_full), axis=1)
                xy_all_nodes_iti.append(
                    (xy_full[seek_row:run_row], valid_full_node[seek_row:run_row])
                )
                xy_all_nodes_run.append((xy_full[run_row:], valid_full_node[run_row:]))

            # Use hybrid trajectory for QC overlay
            xy_traj_full = hybrid_xy_full
            traj_valid_full = ~np.any(np.isnan(xy_traj_full), axis=1)
            if settings.filter_frames_no_animal:
                traj_valid_full = traj_valid_full & valid_frames_full
            xy_traj_iti = xy_traj_full[seek_row:run_row]
            valid_traj_iti = traj_valid_full[seek_row:run_row]
            xy_traj_run = xy_traj_full[run_row:]
            valid_traj_run = traj_valid_full[run_row:]

            # QC image attributes (provenance: what went into heatmap/trajectory and why)
            primary_reason = "in_range_fallback" if use_inrange_primary else "spot"
            heatmap_source = (
                ",".join(heatmap_node_names) if heatmap_node_names else primary_trajectory
            )
            qc_attrs = {
                "heatmap_source": heatmap_source,
                "trajectory_source": primary_trajectory,
                "primary_reason": primary_reason,
            }
            ram_geometry_payload = None
            if arena_type == ARENA_TYPE_RADIAL_ARM and isinstance(radial_arm_payload, dict):
                ram_geometry_payload = radial_arm_payload.get("geometry_payload")

            qc_exit_pos = exit_pos
            qc_exit_radius_px = settings.exit_radius_px
            if arena_type == ARENA_TYPE_RADIAL_ARM and ram_geometry_payload:
                qc_exit_arm = _ram_exit_arm_index_for_pipeline(radial_arm_payload, settings)
                hole = radial_arm_exit_hole_from_geometry_payload(
                    ram_geometry_payload,
                    exit_arm_index=qc_exit_arm,
                )
                if hole is not None:
                    qc_exit_pos = (hole[0], hole[1])
                    qc_exit_radius_px = float(hole[2])

            # ITI/WAIT QC image (seek..run band only)
            if run_row > seek_row and xy_traj_iti.shape[0] > 0:
                generate_trial_qc_images(
                    db_path=db_path,
                    key=key,
                    trajectory_xy=xy_traj_iti,
                    trajectory_valid=valid_traj_iti,
                    exit_pos=qc_exit_pos,
                    arena_center_x_px=settings.arena_center_x_px,
                    arena_center_y_px=settings.arena_center_y_px,
                    arena_radius_px=settings.arena_radius_px,
                    px_per_cm=settings.px_per_cm,
                    exit_radius_px=qc_exit_radius_px,
                    ram_geometry_payload=ram_geometry_payload,
                    fps=fps,
                    xy_list_heatmap=xy_all_nodes_iti if xy_all_nodes_iti else None,
                    image_name="composite_iti_wait",
                    qc_attrs=qc_attrs,
                )

            # RUN QC image
            generate_trial_qc_images(
                db_path=db_path,
                key=key,
                trajectory_xy=xy_traj_run,
                trajectory_valid=valid_traj_run,
                exit_pos=qc_exit_pos,
                arena_center_x_px=settings.arena_center_x_px,
                arena_center_y_px=settings.arena_center_y_px,
                arena_radius_px=settings.arena_radius_px,
                px_per_cm=settings.px_per_cm,
                exit_radius_px=qc_exit_radius_px,
                ram_geometry_payload=ram_geometry_payload,
                fps=fps,
                xy_list_heatmap=xy_all_nodes_run if xy_all_nodes_run else None,
                image_name="composite_run",
                qc_attrs=qc_attrs,
            )
        except ImportError:
            pass
        except Exception as e:
            from tqdm import tqdm

            tqdm.write(f"  Warning: Failed to generate QC images: {e}")
    persist_effective_analysis_params(db_path, key, settings)
    return True


def _calculate_spot_xy(
    traces: dict[str, dict[str, np.ndarray]],
    n_frames: int,
) -> np.ndarray:
    """
    Calculate spot position (average of front-body nodes).

    Args:
        traces: Processed traces dictionary
        n_frames: Number of frames

    Returns:
        Array of shape (n_frames, 2) with spot XY positions
    """
    x_arrays = []
    y_arrays = []

    for node_name in SPOT_NODE_NAMES:
        if node_name in traces:
            x_arrays.append(traces[node_name]["x"])
            y_arrays.append(traces[node_name]["y"])

    if not x_arrays:
        # Fall back to any available SLEAP nodes first.
        for node_name in traces:
            if node_name == IN_RANGE_POINT_NAME:
                continue
            x_arrays.append(traces[node_name]["x"])
            y_arrays.append(traces[node_name]["y"])
    if not x_arrays:
        return np.full((n_frames, 2), np.nan)

    x_stack = np.column_stack(x_arrays)
    y_stack = np.column_stack(y_arrays)
    if x_stack.size == 0:
        return np.full((n_frames, 2), np.nan)
    # Per frame: mean over nodes that are finite. If all NaN for that frame, spot is NaN
    # (avoids np.nanmean "Mean of empty slice" when every constituent is missing).
    n_x = np.isfinite(x_stack).sum(axis=1)
    n_y = np.isfinite(y_stack).sum(axis=1)
    spot_x = np.divide(
        np.nansum(x_stack, axis=1),
        n_x,
        out=np.full(n_frames, np.nan, dtype=float),
        where=(n_x > 0),
    )
    spot_y = np.divide(
        np.nansum(y_stack, axis=1),
        n_y,
        out=np.full(n_frames, np.nan, dtype=float),
        where=(n_y > 0),
    )
    return np.column_stack([spot_x, spot_y])


def _calculate_centroid_xy(
    traces: dict[str, dict[str, np.ndarray]],
    n_frames: int,
) -> np.ndarray:
    """
    Calculate centroid position (mean of all SLEAP nodes) from processed traces.
    Excludes in-range node so centroid is SLEAP-only.
    """
    if "centroid" in traces:
        node = traces["centroid"]
        return np.column_stack([node["x"], node["y"]])
    x_arrays = []
    y_arrays = []
    for node_name in traces:
        if node_name == IN_RANGE_POINT_NAME:
            continue
        x_arrays.append(traces[node_name]["x"])
        y_arrays.append(traces[node_name]["y"])
    if not x_arrays:
        return np.full((n_frames, 2), np.nan)
    x_stack = np.column_stack(x_arrays)
    y_stack = np.column_stack(y_arrays)
    if x_stack.size == 0:
        return np.full((n_frames, 2), np.nan)
    n_x = np.isfinite(x_stack).sum(axis=1)
    n_y = np.isfinite(y_stack).sum(axis=1)
    cx = np.divide(
        np.nansum(x_stack, axis=1),
        n_x,
        out=np.full(n_frames, np.nan, dtype=float),
        where=(n_x > 0),
    )
    cy = np.divide(
        np.nansum(y_stack, axis=1),
        n_y,
        out=np.full(n_frames, np.nan, dtype=float),
        where=(n_y > 0),
    )
    return np.column_stack([cx, cy])


def _get_inrange_xy(
    traces: dict[str, dict[str, np.ndarray]],
    n_frames: int,
) -> np.ndarray:
    """
    Get in-range trajectory (single node from controller/legacy). Returns all-NaN if absent.
    """
    if IN_RANGE_POINT_NAME not in traces:
        return np.full((n_frames, 2), np.nan)
    node = traces[IN_RANGE_POINT_NAME]
    return np.column_stack([node["x"], node["y"]])


def _max_gap_in_trace(xy: np.ndarray, valid: np.ndarray) -> int:
    """
    Maximum run length of invalid (False) frames in valid mask.
    Used to decide primary trajectory: if spot has gap > TRACE_MAX_GAP_FRAMES, use in-range.
    """
    if valid.size == 0:
        return 0
    invalid = ~np.asarray(valid, dtype=bool)
    if not np.any(invalid):
        return 0
    # Run-length of invalid
    changes = np.diff(np.concatenate([[False], invalid, [False]]).astype(np.int8))
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]
    if len(starts) == 0 or len(ends) == 0:
        return int(np.sum(invalid))
    lengths = ends - starts
    return int(np.max(lengths)) if len(lengths) else 0
