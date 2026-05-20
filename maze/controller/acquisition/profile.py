"""Profile save/load for shared acquisition config plus task-owned payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

from ...core.tasks import ARENA_TYPE_RADIAL_ARM, normalize_arena_type
from .radial_arm.config import (
    RadialArmCalibrationConfig,
    RadialArmControllerConfig,
    RadialArmTaskConfig,
    RadialArmTemplateConfig,
    ram_apothem_cm_from_template,
    sync_ram_px_per_cm,
)
from .shared_config import (
    AcquisitionConfig,
    AnalysisTraceQualityConfig,
    AnalysisTrajectoryConfig,
    AnimalInfo,
    FallbackTrackingConfig,
    SessionConfig,
)
from .vast.config import (
    ArenaConfig,
    ExitAngleConfig,
    FT_TO_CM,
    StimulusConfig,
    VastControllerConfig,
    VastTaskConfig,
)

ProfileTaskMode = Literal["vast", "ram"]


class ProfileTaskMismatchError(ValueError):
    """Raised when a profile JSON belongs to a different acquisition task than the shell."""


def profile_task_mode_from_dict(data: Dict[str, Any]) -> ProfileTaskMode:
    """Infer ``vast`` vs ``ram`` from raw profile JSON (before building config objects)."""
    common = data.get("common", data)
    arena_type = normalize_arena_type(
        str(common.get("arena_type", data.get("arena_type", "circular")) or "circular")
    )
    if arena_type == ARENA_TYPE_RADIAL_ARM:
        return "ram"
    return "vast"


def read_profile_task_mode(path: Path) -> ProfileTaskMode:
    """Read a profile file and return which acquisition task it was saved for."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return profile_task_mode_from_dict(data)


def _arena_to_dict(config: ArenaConfig) -> Dict[str, Any]:
    return {
        "diameter_cm": config.diameter_cm,
        "diameter_display_unit": config.diameter_display_unit,
        "radius_px": config.radius_px,
        "tracking_radius_px": config.tracking_radius_px,
        "center_pct": config.center_pct,
        "exit_radius_cm": config.exit_radius_cm,
        "arena_center_x_px": config.arena_center_x_px,
        "arena_center_y_px": config.arena_center_y_px,
    }


def _arena_from_dict(data: Dict[str, Any]) -> ArenaConfig:
    diameter_cm = data.get("diameter_cm")
    if diameter_cm is None:
        diameter_cm = float(data.get("diameter_ft", 4.0)) * FT_TO_CM
    else:
        diameter_cm = float(diameter_cm)
    radius_px = data.get("radius_px")
    if radius_px is None and "px_per_cm" in data:
        radius_px = (diameter_cm / 2.0) * float(data["px_per_cm"])
    radius_px = float(radius_px) if radius_px is not None else 0.0
    tracking_radius_px = data.get("tracking_radius_px")
    tracking_radius_px = float(tracking_radius_px) if tracking_radius_px is not None else 0.0
    return ArenaConfig(
        diameter_cm=diameter_cm,
        diameter_display_unit=str(data.get("diameter_display_unit", "ft")),
        radius_px=radius_px,
        tracking_radius_px=tracking_radius_px,
        center_pct=float(data.get("center_pct", 0.5)),
        exit_radius_cm=float(data.get("exit_radius_cm", 5.0)),
        arena_center_x_px=float(data.get("arena_center_x_px", 0.0)),
        arena_center_y_px=float(data.get("arena_center_y_px", 0.0)),
    )


def _exit_angles_to_dict(config: ExitAngleConfig) -> Dict[str, Any]:
    return {
        "n_angles": config.n_angles,
        "offset_deg": config.offset_deg,
        "step_deg": config.step_deg,
        "default_manual_exit_index": int(getattr(config, "default_manual_exit_index", 0)),
    }


def _exit_angles_from_dict(data: Dict[str, Any]) -> ExitAngleConfig:
    return ExitAngleConfig(
        n_angles=int(data.get("n_angles", 4)),
        offset_deg=float(data.get("offset_deg", -30.0)),
        step_deg=float(data.get("step_deg", 20.0)),
        default_manual_exit_index=int(data.get("default_manual_exit_index", 0)),
    )


def _stimulus_to_dict(config: StimulusConfig) -> Dict[str, Any]:
    return {
        "min_at_exit": config.min_at_exit,
        "min_duty_pct": config.min_duty_pct,
        "max_duty_pct": config.max_duty_pct,
    }


def _stimulus_from_dict(data: Dict[str, Any]) -> StimulusConfig:
    return StimulusConfig(
        min_at_exit=bool(data.get("min_at_exit", True)),
        min_duty_pct=float(data.get("min_duty_pct", 35.0)),
        max_duty_pct=float(data.get("max_duty_pct", 85.0)),
    )


def _animal_to_dict(animal: AnimalInfo) -> Dict[str, Any]:
    return {
        "animal_id": animal.animal_id,
        "tx": animal.tx,
        "strain": animal.strain,
        "sex": animal.sex,
        "drug": animal.drug,
        "experiment": animal.experiment,
        "researcher": animal.researcher,
        "notes": animal.notes,
    }


def _animal_from_dict(data: Dict[str, Any]) -> AnimalInfo:
    return AnimalInfo(
        animal_id=str(data.get("animal_id", "")),
        tx=data.get("tx"),
        strain=data.get("strain"),
        sex=data.get("sex"),
        drug=data.get("drug"),
        experiment=data.get("experiment"),
        researcher=data.get("researcher"),
        notes=data.get("notes"),
    )


def _session_to_dict(config: SessionConfig) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "num_animals": config.num_animals,
        "num_trials": config.num_trials,
        "max_trial_duration_s": config.max_trial_duration_s,
        "iti_s": config.iti_s,
        "seed_mode": config.seed_mode,
        "seed_auto_value": config.seed_auto_value,
        "seed_legacy_source": config.seed_legacy_source,
        "animals": [_animal_to_dict(animal) for animal in config.animals],
    }
    if config.exit_schedule_indices is not None:
        d["exit_schedule_indices"] = list(config.exit_schedule_indices)
    return d


def _session_from_dict(data: Dict[str, Any]) -> SessionConfig:
    animals = [_animal_from_dict(item) for item in data.get("animals", [])]
    mode = str(data.get("seed_mode", "auto") or "auto").strip().lower()
    if mode not in ("auto", "legacy", "manual"):
        mode = "auto"
    schedule_raw = data.get("exit_schedule_indices")
    schedule_indices: Optional[list[int]] = None
    if isinstance(schedule_raw, list) and schedule_raw:
        schedule_indices = [int(x) for x in schedule_raw]
    return SessionConfig(
        num_animals=int(data.get("num_animals", 1)),
        num_trials=int(data.get("num_trials", 9)),
        max_trial_duration_s=float(data.get("max_trial_duration_s", 300.0)),
        iti_s=float(data.get("iti_s", 30.0)),
        seed_mode=mode,
        seed_auto_value=(
            int(data["seed_auto_value"]) if data.get("seed_auto_value") is not None else None
        ),
        seed_legacy_source=data.get("seed_legacy_source"),
        exit_schedule_indices=schedule_indices,
        animals=animals,
    )


def _fallback_tracking_to_dict(config: FallbackTrackingConfig) -> Dict[str, Any]:
    return {
        "min_area": config.min_area,
        "max_area": config.max_area,
        "morph_kernel_size": config.morph_kernel_size,
        "max_jump_px": config.max_jump_px,
        "selection_mode": config.selection_mode,
        "min_circularity": config.min_circularity,
        "range_low": config.range_low,
        "range_high": config.range_high,
        "range_from_next_click": config.range_from_next_click,
        "range_pick_delta": config.range_pick_delta,
        "range_pick_half": config.range_pick_half,
        "node_max_jump_px": config.node_max_jump_px,
        "node_jump_confirm_frames": config.node_jump_confirm_frames,
        "min_sleap_nodes": config.min_sleap_nodes,
        "show_blob_overlay": config.show_blob_overlay,
        "max_contours": config.max_contours,
    }


def _fallback_tracking_from_dict(data: Dict[str, Any]) -> FallbackTrackingConfig:
    return FallbackTrackingConfig(
        min_area=int(data.get("min_area", 80)),
        max_area=int(data.get("max_area", 0)),
        morph_kernel_size=int(data.get("morph_kernel_size", 5)),
        max_jump_px=float(data.get("max_jump_px", 0.0)),
        selection_mode=str(data.get("selection_mode", "closest_else_largest")),
        min_circularity=float(data.get("min_circularity", 0.0)),
        range_low=int(data.get("range_low", 0)),
        range_high=int(data.get("range_high", 255)),
        range_from_next_click=bool(data.get("range_from_next_click", False)),
        range_pick_delta=max(0, int(data.get("range_pick_delta", 12))),
        range_pick_half=max(0, int(data.get("range_pick_half", 2))),
        node_max_jump_px=float(data.get("node_max_jump_px", 0.0)),
        node_jump_confirm_frames=max(1, int(data.get("node_jump_confirm_frames", 2))),
        min_sleap_nodes=int(data.get("min_sleap_nodes", 1)),
        show_blob_overlay=bool(data.get("show_blob_overlay", True)),
        max_contours=int(data.get("max_contours", 0)),
    )


def _analysis_trajectory_to_dict(config: AnalysisTrajectoryConfig) -> Dict[str, Any]:
    return {
        "movement_start_threshold_m_per_frame": config.movement_start_threshold_m_per_frame,
        "movement_stop_threshold_m_per_frame": config.movement_stop_threshold_m_per_frame,
        "movement_speed_median_window_frames": config.movement_speed_median_window_frames,
        "movement_entry_debounce_frames": config.movement_entry_debounce_frames,
        "movement_exit_debounce_frames": config.movement_exit_debounce_frames,
        "min_movement_bout_duration_frames": config.min_movement_bout_duration_frames,
        "movement_inter_bout_interval_frames": config.movement_inter_bout_interval_frames,
        "max_movement_per_frame_cm": config.max_movement_per_frame_cm,
        "jump_filter_lookahead_frames": config.jump_filter_lookahead_frames,
    }


def _analysis_trajectory_from_dict(data: Dict[str, Any]) -> AnalysisTrajectoryConfig:
    from maze.pipeline.defaults import (
        JUMP_FILTER_LOOKAHEAD_FRAMES,
        MAX_MOVEMENT_PER_FRAME_CM,
        MOVEMENT_ENTRY_DEBOUNCE_FRAMES,
        MOVEMENT_EXIT_DEBOUNCE_FRAMES,
        MOVEMENT_INTER_BOUT_INTERVAL_FRAMES,
        MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES,
        MOVEMENT_START_THRESHOLD_M_PER_FRAME,
        MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
        MIN_MOVEMENT_BOUT_DURATION_FRAMES,
    )

    return AnalysisTrajectoryConfig(
        movement_start_threshold_m_per_frame=float(
            data.get(
                "movement_start_threshold_m_per_frame",
                MOVEMENT_START_THRESHOLD_M_PER_FRAME,
            )
        ),
        movement_stop_threshold_m_per_frame=float(
            data.get(
                "movement_stop_threshold_m_per_frame",
                MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
            )
        ),
        movement_speed_median_window_frames=max(
            1,
            int(
                data.get(
                    "movement_speed_median_window_frames",
                    MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES,
                )
            ),
        ),
        movement_entry_debounce_frames=max(
            1,
            int(
                data.get(
                    "movement_entry_debounce_frames",
                    MOVEMENT_ENTRY_DEBOUNCE_FRAMES,
                )
            ),
        ),
        movement_exit_debounce_frames=max(
            1,
            int(
                data.get(
                    "movement_exit_debounce_frames",
                    MOVEMENT_EXIT_DEBOUNCE_FRAMES,
                )
            ),
        ),
        min_movement_bout_duration_frames=max(
            1,
            int(
                data.get(
                    "min_movement_bout_duration_frames",
                    MIN_MOVEMENT_BOUT_DURATION_FRAMES,
                )
            ),
        ),
        movement_inter_bout_interval_frames=max(
            0,
            int(
                data.get(
                    "movement_inter_bout_interval_frames",
                    MOVEMENT_INTER_BOUT_INTERVAL_FRAMES,
                )
            ),
        ),
        max_movement_per_frame_cm=float(
            data.get("max_movement_per_frame_cm", MAX_MOVEMENT_PER_FRAME_CM)
        ),
        jump_filter_lookahead_frames=max(
            0,
            int(
                data.get(
                    "jump_filter_lookahead_frames",
                    JUMP_FILTER_LOOKAHEAD_FRAMES,
                )
            ),
        ),
    )


def _analysis_trace_quality_to_dict(
    config: AnalysisTraceQualityConfig,
) -> Dict[str, Any]:
    return {
        "filter_frames_no_animal": config.filter_frames_no_animal,
        "min_confident_nodes_per_frame": config.min_confident_nodes_per_frame,
        "min_node_confidence_threshold": config.min_node_confidence_threshold,
        "min_valid_frame_run_length": config.min_valid_frame_run_length,
        "min_mean_confidence_per_frame": config.min_mean_confidence_per_frame,
        "trace_interpolate_nans": config.trace_interpolate_nans,
        "trace_max_gap_frames": config.trace_max_gap_frames,
        "trace_interpolate_low_conf": config.trace_interpolate_low_conf,
        "trace_confidence_threshold": config.trace_confidence_threshold,
        "trace_apply_smoothing": config.trace_apply_smoothing,
        "trace_smoothing_window": config.trace_smoothing_window,
    }


def _analysis_trace_quality_from_dict(
    data: Dict[str, Any],
) -> AnalysisTraceQualityConfig:
    from maze.pipeline.defaults import (
        FILTER_FRAMES_NO_ANIMAL,
        MIN_CONFIDENT_NODES_PER_FRAME,
        MIN_MEAN_CONFIDENCE_PER_FRAME,
        MIN_NODE_CONFIDENCE_THRESHOLD,
        MIN_VALID_FRAME_RUN_LENGTH,
        TRACE_APPLY_SMOOTHING,
        TRACE_CONFIDENCE_THRESHOLD,
        TRACE_INTERPOLATE_LOW_CONF,
        TRACE_INTERPOLATE_NANS,
        TRACE_MAX_GAP_FRAMES,
        TRACE_SMOOTHING_WINDOW,
    )

    mean_conf = data.get("min_mean_confidence_per_frame", MIN_MEAN_CONFIDENCE_PER_FRAME)
    return AnalysisTraceQualityConfig(
        filter_frames_no_animal=bool(data.get("filter_frames_no_animal", FILTER_FRAMES_NO_ANIMAL)),
        min_confident_nodes_per_frame=max(
            0,
            int(
                data.get(
                    "min_confident_nodes_per_frame",
                    MIN_CONFIDENT_NODES_PER_FRAME,
                )
            ),
        ),
        min_node_confidence_threshold=float(
            data.get(
                "min_node_confidence_threshold",
                MIN_NODE_CONFIDENCE_THRESHOLD,
            )
        ),
        min_valid_frame_run_length=max(
            0,
            int(
                data.get(
                    "min_valid_frame_run_length",
                    MIN_VALID_FRAME_RUN_LENGTH,
                )
            ),
        ),
        min_mean_confidence_per_frame=(float(mean_conf) if mean_conf is not None else None),
        trace_interpolate_nans=bool(data.get("trace_interpolate_nans", TRACE_INTERPOLATE_NANS)),
        trace_max_gap_frames=max(
            0,
            int(data.get("trace_max_gap_frames", TRACE_MAX_GAP_FRAMES)),
        ),
        trace_interpolate_low_conf=bool(
            data.get("trace_interpolate_low_conf", TRACE_INTERPOLATE_LOW_CONF)
        ),
        trace_confidence_threshold=float(
            data.get("trace_confidence_threshold", TRACE_CONFIDENCE_THRESHOLD)
        ),
        trace_apply_smoothing=bool(data.get("trace_apply_smoothing", TRACE_APPLY_SMOOTHING)),
        trace_smoothing_window=max(
            1,
            int(data.get("trace_smoothing_window", TRACE_SMOOTHING_WINDOW)),
        ),
    )


def _shared_to_dict(config: AcquisitionConfig) -> Dict[str, Any]:
    return {
        "session": _session_to_dict(config.session),
        "output_dir": str(config.output_dir) if config.output_dir else None,
        "h5_filename": config.h5_filename,
        "arena_type": config.arena_type,
        "run_mode": config.run_mode,
        "run_analysis_after_trial": config.run_analysis_after_trial,
        "virtual_duration_override_s": (
            float(config.virtual_duration_override_s)
            if config.virtual_duration_override_s is not None
            else None
        ),
        "fallback_tracking": _fallback_tracking_to_dict(config.fallback_tracking),
        "sleap_confidence_pct": config.sleap_confidence_pct,
        "sleap_every_n": config.sleap_every_n,
        "sleap_exit_min_keypoints": config.sleap_exit_min_keypoints,
        "fallback_exit_blob_overlap_pct": config.fallback_exit_blob_overlap_pct,
        "track_exit_either_success": config.track_exit_either_success,
        "sleap_model_path": config.sleap_model_path or "",
        "track_show": config.track_show,
        "track_async": config.track_async,
        "track_enable_backup": config.track_enable_backup,
        "track_enable_sleap": config.track_enable_sleap,
        "overlay_opacity_pct": config.overlay_opacity_pct,
        "arduino_port": config.arduino_port,
        "preview_set_center_from_next_click": bool(
            getattr(config, "preview_set_center_from_next_click", False)
        ),
        "analysis_trajectory": _analysis_trajectory_to_dict(config.analysis_trajectory),
        "analysis_trace_quality": _analysis_trace_quality_to_dict(config.analysis_trace_quality),
    }


def _enable_backup_sleap_from_dict(data: Dict[str, Any]) -> tuple[bool, bool]:
    """Parse backup/SLEAP toggles; migrate legacy ``track_backup_only``."""
    eb = data.get("track_enable_backup")
    es = data.get("track_enable_sleap")
    if eb is not None or es is not None:
        return (
            bool(eb if eb is not None else True),
            bool(es if es is not None else True),
        )
    legacy = data.get("track_backup_only")
    if legacy is not None:
        return True, not bool(legacy)
    return True, True


def _run_mode_from_dict(data: Dict[str, Any]) -> str:
    value = str(data.get("run_mode", "continuous") or "continuous").strip().lower()
    return value if value in ("continuous", "alternating") else "continuous"


def _shared_kwargs_from_dict(
    data: Dict[str, Any],
    *,
    arena_type: str,
    default_h5_filename: str,
) -> Dict[str, Any]:
    output_dir = data.get("output_dir")
    _eb, _es = _enable_backup_sleap_from_dict(data)
    return {
        "session": _session_from_dict(data.get("session", {})),
        "output_dir": output_dir if output_dir else None,
        "h5_filename": str(
            data.get("h5_filename", default_h5_filename) or default_h5_filename
        ).strip()
        or default_h5_filename,
        "arena_type": arena_type,
        "run_mode": _run_mode_from_dict(data),
        "run_analysis_after_trial": bool(data.get("run_analysis_after_trial", False)),
        "virtual_duration_override_s": (
            float(data.get("virtual_duration_override_s"))
            if data.get("virtual_duration_override_s") is not None
            else None
        ),
        "fallback_tracking": _fallback_tracking_from_dict(data.get("fallback_tracking", {})),
        "sleap_confidence_pct": int(data.get("sleap_confidence_pct", 50)),
        "sleap_every_n": max(1, min(5, int(data.get("sleap_every_n", 1)))),
        "sleap_exit_min_keypoints": max(1, int(data.get("sleap_exit_min_keypoints", 2))),
        "fallback_exit_blob_overlap_pct": max(
            0.0, min(100.0, float(data.get("fallback_exit_blob_overlap_pct", 15.0)))
        ),
        "track_exit_either_success": bool(data.get("track_exit_either_success", False)),
        "sleap_model_path": str(data.get("sleap_model_path", "") or "").strip(),
        "track_show": bool(data.get("track_show", True)),
        "track_async": bool(data.get("track_async", False)),
        "track_enable_backup": _eb,
        "track_enable_sleap": _es,
        "overlay_opacity_pct": max(0, min(100, int(data.get("overlay_opacity_pct", 70)))),
        "arduino_port": data.get("arduino_port") or None,
        "preview_set_center_from_next_click": bool(
            data.get("preview_set_center_from_next_click", False)
        ),
        "analysis_trajectory": _analysis_trajectory_from_dict(data.get("analysis_trajectory", {})),
        "analysis_trace_quality": _analysis_trace_quality_from_dict(
            data.get("analysis_trace_quality", {})
        ),
    }


def _vast_task_to_dict(config: VastTaskConfig) -> Dict[str, Any]:
    return {
        "arena": _arena_to_dict(config.arena),
        "exit_angles": _exit_angles_to_dict(config.exit_angles),
        "stimulus": _stimulus_to_dict(config.stimulus),
        "run_phase": config.run_phase,
        "hab_training_duty_pct": config.hab_training_duty_pct,
        "wait_not_center_duty_pct": config.wait_not_center_duty_pct,
    }


def _vast_task_from_dict(data: Dict[str, Any]) -> VastTaskConfig:
    return VastTaskConfig(
        arena=_arena_from_dict(data.get("arena", {})),
        exit_angles=_exit_angles_from_dict(data.get("exit_angles", {})),
        stimulus=_stimulus_from_dict(data.get("stimulus", {})),
        run_phase=str(data.get("run_phase", "habituation") or "habituation").strip()
        or "habituation",
        hab_training_duty_pct=float(data.get("hab_training_duty_pct", 60.0)),
        wait_not_center_duty_pct=float(data.get("wait_not_center_duty_pct", 0.0)),
    )


def _radial_arm_task_to_dict(config: RadialArmTaskConfig) -> Dict[str, Any]:
    return {
        "template": {
            "center_midedge_to_midedge_cm": config.template.center_midedge_to_midedge_cm,
            "arm_length_cm": config.template.arm_length_cm,
            "arm_width_cm": config.template.arm_width_cm,
            "arm_split_cm": config.template.arm_split_cm,
            "hole_radius_cm": config.template.hole_radius_cm,
            "hole_inset_from_arm_end_cm": config.template.hole_inset_from_arm_end_cm,
        },
        "calibration": {
            "template_center_x_px": config.calibration.template_center_x_px,
            "template_center_y_px": config.calibration.template_center_y_px,
            "template_rotation_deg": config.calibration.template_rotation_deg,
            "apothem_px": config.calibration.apothem_px,
            "px_per_cm": config.calibration.px_per_cm,
            "tracking_mask_margin_px": config.calibration.tracking_mask_margin_px,
            "edit_region_name": config.calibration.edit_region_name,
        },
        "exit_arm_index": config.exit_arm_index,
        "speaker_device_name": config.speaker_device_name,
        "speaker_volume_pct": config.speaker_volume_pct,
        "stimulus_frequency_hz": config.stimulus_frequency_hz,
        "stimulus_enabled": config.stimulus_enabled,
    }


def _radial_arm_calibration_from_dict(
    calibration_data: Dict[str, Any],
    *,
    template: RadialArmTemplateConfig,
) -> RadialArmCalibrationConfig:
    ap_cm = ram_apothem_cm_from_template(template)
    ap_px = float(calibration_data.get("apothem_px", 0.0))
    px_legacy = float(calibration_data.get("px_per_cm", 0.0))
    if ap_px <= 0.0 and px_legacy > 0.0 and ap_cm > 0.0:
        ap_px = px_legacy * ap_cm
    return RadialArmCalibrationConfig(
        template_center_x_px=float(calibration_data.get("template_center_x_px", 0.0)),
        template_center_y_px=float(calibration_data.get("template_center_y_px", 0.0)),
        template_rotation_deg=float(calibration_data.get("template_rotation_deg", 0.0)),
        apothem_px=ap_px,
        px_per_cm=0.0,
        tracking_mask_margin_px=float(calibration_data.get("tracking_mask_margin_px", 0.0)),
        edit_region_name=str(calibration_data.get("edit_region_name", "") or ""),
    )


def _radial_arm_task_from_dict(data: Dict[str, Any]) -> RadialArmTaskConfig:
    template_data = data.get("template", {}) if isinstance(data, dict) else {}
    calibration_data = data.get("calibration", {}) if isinstance(data, dict) else {}
    template = RadialArmTemplateConfig(
        center_midedge_to_midedge_cm=float(template_data.get("center_midedge_to_midedge_cm", 80.0)),
        arm_length_cm=float(template_data.get("arm_length_cm", 55.0)),
        arm_width_cm=float(template_data.get("arm_width_cm", 15.0)),
        arm_split_cm=float(template_data.get("arm_split_cm", 27.5)),
        hole_radius_cm=float(template_data.get("hole_radius_cm", 5.0)),
        hole_inset_from_arm_end_cm=float(template_data.get("hole_inset_from_arm_end_cm", 10.0)),
    )
    ram = RadialArmTaskConfig(
        template=template,
        calibration=_radial_arm_calibration_from_dict(
            calibration_data,
            template=template,
        ),
        exit_arm_index=int(data.get("exit_arm_index", 0)),
        speaker_device_name=str(data.get("speaker_device_name", "") or ""),
        speaker_volume_pct=float(data.get("speaker_volume_pct", 100.0)),
        stimulus_frequency_hz=float(data.get("stimulus_frequency_hz", 5000.0)),
        stimulus_enabled=bool(data.get("stimulus_enabled", False)),
    )
    sync_ram_px_per_cm(ram)
    return ram


def config_to_dict(config: AcquisitionConfig) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "schema_version": 3,
        "common": _shared_to_dict(config),
    }
    if isinstance(config, RadialArmControllerConfig):
        data["radial_arm"] = _radial_arm_task_to_dict(config.radial_arm)
    elif isinstance(config, VastControllerConfig):
        data["vast"] = _vast_task_to_dict(config.vast)
    return data


def gui_to_dict(
    *,
    track_show: bool = False,
    track_async: bool = False,
    track_enable_backup: bool = True,
    track_enable_sleap: bool = True,
    track_sleap_path: str = "",
    track_confidence: int = 50,
    track_sleap_every_n: int = 1,
    track_opacity: int = 70,
    display_brightness: int = 0,
    display_contrast: int = 100,
    camera_flip: bool = False,
    camera_source: str = "OpenCV",
    camera_device: int = 0,
    arduino_port: str = "",
) -> Dict[str, Any]:
    """Build dict of GUI-only settings for profile save."""
    return {
        "track_show": track_show,
        "track_async": track_async,
        "track_enable_backup": track_enable_backup,
        "track_enable_sleap": track_enable_sleap,
        "track_sleap_path": track_sleap_path,
        "track_confidence": track_confidence,
        "track_sleap_every_n": track_sleap_every_n,
        "track_opacity": track_opacity,
        "display_brightness": display_brightness,
        "display_contrast": display_contrast,
        "camera_flip": camera_flip,
        "camera_source": camera_source,
        "camera_device": camera_device,
        "arduino_port": arduino_port or "",
    }


def gui_from_dict(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return gui dict for applying to UI; None if missing or empty."""
    if not data or not isinstance(data, dict):
        return None
    return data


def config_from_dict(data: Dict[str, Any]) -> AcquisitionConfig:
    common = data.get("common", data)
    arena_type = normalize_arena_type(
        str(common.get("arena_type", data.get("arena_type", "circular")) or "circular")
    )
    if arena_type == ARENA_TYPE_RADIAL_ARM:
        shared_kwargs = _shared_kwargs_from_dict(
            common,
            arena_type=arena_type,
            default_h5_filename="ram_trials.h5",
        )
        radial_arm = _radial_arm_task_from_dict(data.get("radial_arm", {}))
        return RadialArmControllerConfig(**shared_kwargs, radial_arm=radial_arm)

    shared_kwargs = _shared_kwargs_from_dict(
        common,
        arena_type=arena_type,
        default_h5_filename="trials.h5",
    )
    vast_payload = data.get("vast", data)
    return VastControllerConfig(
        **shared_kwargs,
        vast=_vast_task_from_dict(vast_payload),
    )


def save_profile(
    config: AcquisitionConfig,
    path: Path,
    *,
    session_id: Optional[str] = None,
    trial_idx: Optional[int] = None,
    slot_idx: Optional[int] = None,
    gui: Optional[Dict[str, Any]] = None,
) -> None:
    """Write profile JSON, optionally including last session/trial/slot state and GUI settings."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config_to_dict(config)
    if session_id is not None:
        data["last_session_id"] = session_id
    if trial_idx is not None:
        data["last_trial_idx"] = trial_idx
    if slot_idx is not None:
        data["last_slot_idx"] = slot_idx
    if gui is not None:
        data["gui"] = gui
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def _merge_gui_into_config(config: AcquisitionConfig, gui: Optional[Dict[str, Any]]) -> None:
    """Apply legacy GUI dict keys into config for backward compatibility."""
    if not gui or not isinstance(gui, dict):
        return
    if "track_sleap_path" in gui:
        config.sleap_model_path = str(gui.get("track_sleap_path") or "").strip()
    if gui.get("track_show") is not None:
        config.track_show = bool(gui["track_show"])
    if gui.get("track_async") is not None:
        config.track_async = bool(gui["track_async"])
    if gui.get("track_enable_backup") is not None:
        config.track_enable_backup = bool(gui["track_enable_backup"])
    if gui.get("track_enable_sleap") is not None:
        config.track_enable_sleap = bool(gui["track_enable_sleap"])
    elif gui.get("track_backup_only") is not None:
        config.track_enable_backup = True
        config.track_enable_sleap = not bool(gui["track_backup_only"])
    if gui.get("track_opacity") is not None:
        config.overlay_opacity_pct = max(0, min(100, int(gui["track_opacity"])))
    if gui.get("arduino_port") is not None:
        config.arduino_port = str(gui["arduino_port"]).strip() or None


def load_profile(
    path: Path,
    *,
    expected_task_mode: Optional[ProfileTaskMode] = None,
) -> Tuple[AcquisitionConfig, str, int, Optional[Dict[str, Any]], Optional[int]]:
    """Load profile JSON and return config plus last session/trial/slot GUI state."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    profile_mode = profile_task_mode_from_dict(data)
    if expected_task_mode is not None and profile_mode != expected_task_mode:
        want = "RAM" if profile_mode == "ram" else "VAST"
        cli = "uv run maze-daq --ram" if profile_mode == "ram" else "uv run maze-daq --vast"
        raise ProfileTaskMismatchError(
            f"This profile was saved for {want} mode. Start acquisition with `{cli}` "
            f"to load it, or choose a profile saved from the current task."
        )
    config = config_from_dict(data)
    gui = gui_from_dict(data.get("gui"))
    _merge_gui_into_config(config, gui)
    n_trials = config.session.num_trials
    n_animals = config.session.num_animals
    total_slots = n_animals * n_trials
    last_session_id = data.get("last_session_id")
    if last_session_id is None and "last_session_idx" in data:
        last_session_id = f"S{int(data['last_session_idx']) + 1:02d}"
    if last_session_id is None:
        last_session_id = ""
    session_id = str(last_session_id) if last_session_id else ""
    trial_idx = max(0, min(int(data.get("last_trial_idx", 0)), n_trials - 1)) if n_trials else 0
    slot_idx = data.get("last_slot_idx")
    if slot_idx is not None:
        slot_idx = max(0, min(int(slot_idx), total_slots)) if total_slots else 0
    return config, session_id, trial_idx, gui, slot_idx


def save_analysis_profile(
    *,
    analysis_trajectory: AnalysisTrajectoryConfig,
    analysis_trace_quality: AnalysisTraceQualityConfig | None = None,
    path: Path,
) -> None:
    """Save only analysis settings (separate from acquisition profiles)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tq = analysis_trace_quality or AnalysisTraceQualityConfig()
    data: Dict[str, Any] = {
        "schema_version": 2,
        "kind": "analysis_profile",
        "analysis_trajectory": _analysis_trajectory_to_dict(analysis_trajectory),
        "analysis_trace_quality": _analysis_trace_quality_to_dict(tq),
    }
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def load_analysis_profile(
    path: Path,
) -> tuple[AnalysisTrajectoryConfig, AnalysisTraceQualityConfig]:
    """Load analysis settings profile saved by :func:`save_analysis_profile`."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Invalid analysis profile format.")
    if str(data.get("kind", "")).strip().lower() not in ("", "analysis_profile"):
        raise ValueError("This file is not an analysis settings profile.")
    traj = _analysis_trajectory_from_dict(data.get("analysis_trajectory", {}))
    tq_raw = data.get("analysis_trace_quality")
    trace_q = (
        _analysis_trace_quality_from_dict(tq_raw)
        if isinstance(tq_raw, dict)
        else AnalysisTraceQualityConfig()
    )
    return traj, trace_q
