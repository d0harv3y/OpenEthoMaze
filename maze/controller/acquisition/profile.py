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
)
from .shared_config import AcquisitionConfig, AnimalInfo, FallbackTrackingConfig, SessionConfig
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
    tracking_radius_px = (
        float(tracking_radius_px) if tracking_radius_px is not None else 0.0
    )
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
    }


def _exit_angles_from_dict(data: Dict[str, Any]) -> ExitAngleConfig:
    return ExitAngleConfig(
        n_angles=int(data.get("n_angles", 4)),
        offset_deg=float(data.get("offset_deg", -30.0)),
        step_deg=float(data.get("step_deg", 20.0)),
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
        "notes": animal.notes,
    }


def _animal_from_dict(data: Dict[str, Any]) -> AnimalInfo:
    return AnimalInfo(
        animal_id=str(data.get("animal_id", "")),
        tx=data.get("tx"),
        strain=data.get("strain"),
        sex=data.get("sex"),
        drug=data.get("drug"),
        notes=data.get("notes"),
    )


def _session_to_dict(config: SessionConfig) -> Dict[str, Any]:
    return {
        "num_animals": config.num_animals,
        "num_trials": config.num_trials,
        "max_trial_duration_s": config.max_trial_duration_s,
        "iti_s": config.iti_s,
        "seed": config.seed,
        "legacy_seed_db_path": config.legacy_seed_db_path,
        "animals": [_animal_to_dict(animal) for animal in config.animals],
    }


def _session_from_dict(data: Dict[str, Any]) -> SessionConfig:
    animals = [_animal_from_dict(item) for item in data.get("animals", [])]
    return SessionConfig(
        num_animals=int(data.get("num_animals", 1)),
        num_trials=int(data.get("num_trials", 9)),
        max_trial_duration_s=float(data.get("max_trial_duration_s", 300.0)),
        iti_s=float(data.get("iti_s", 30.0)),
        seed=data.get("seed"),
        legacy_seed_db_path=data.get("legacy_seed_db_path"),
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
        node_max_jump_px=float(data.get("node_max_jump_px", 0.0)),
        node_jump_confirm_frames=max(1, int(data.get("node_jump_confirm_frames", 2))),
        min_sleap_nodes=int(data.get("min_sleap_nodes", 1)),
        show_blob_overlay=bool(data.get("show_blob_overlay", True)),
        max_contours=int(data.get("max_contours", 0)),
    )


def _shared_to_dict(config: AcquisitionConfig) -> Dict[str, Any]:
    return {
        "session": _session_to_dict(config.session),
        "output_dir": str(config.output_dir) if config.output_dir else None,
        "h5_filename": config.h5_filename,
        "arena_type": config.arena_type,
        "run_mode": config.run_mode,
        "run_analysis_after_trial": config.run_analysis_after_trial,
        "fallback_tracking": _fallback_tracking_to_dict(config.fallback_tracking),
        "sleap_confidence_pct": config.sleap_confidence_pct,
        "sleap_every_n": config.sleap_every_n,
        "sleap_exit_min_keypoints": config.sleap_exit_min_keypoints,
        "fallback_exit_blob_overlap_pct": config.fallback_exit_blob_overlap_pct,
        "track_exit_either_success": config.track_exit_either_success,
        "sleap_model_path": config.sleap_model_path or "",
        "track_show": config.track_show,
        "track_async": config.track_async,
        "track_backup_only": config.track_backup_only,
        "overlay_opacity_pct": config.overlay_opacity_pct,
        "arduino_port": config.arduino_port,
    }


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
        "fallback_tracking": _fallback_tracking_from_dict(
            data.get("fallback_tracking", {})
        ),
        "sleap_confidence_pct": int(data.get("sleap_confidence_pct", 50)),
        "sleap_every_n": max(1, min(5, int(data.get("sleap_every_n", 1)))),
        "sleap_exit_min_keypoints": max(
            1, int(data.get("sleap_exit_min_keypoints", 2))
        ),
        "fallback_exit_blob_overlap_pct": max(
            0.0, min(100.0, float(data.get("fallback_exit_blob_overlap_pct", 15.0)))
        ),
        "track_exit_either_success": bool(data.get("track_exit_either_success", False)),
        "sleap_model_path": str(data.get("sleap_model_path", "") or "").strip(),
        "track_show": bool(data.get("track_show", True)),
        "track_async": bool(data.get("track_async", False)),
        "track_backup_only": bool(data.get("track_backup_only", False)),
        "overlay_opacity_pct": max(
            0, min(100, int(data.get("overlay_opacity_pct", 70)))
        ),
        "arduino_port": data.get("arduino_port") or None,
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
        run_phase=str(data.get("run_phase", "habituation") or "habituation")
        .strip()
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
            "hole_arm_index": config.template.hole_arm_index,
            "hole_radius_cm": config.template.hole_radius_cm,
            "hole_inset_from_arm_end_cm": config.template.hole_inset_from_arm_end_cm,
        },
        "calibration": {
            "template_center_x_px": config.calibration.template_center_x_px,
            "template_center_y_px": config.calibration.template_center_y_px,
            "template_rotation_deg": config.calibration.template_rotation_deg,
            "px_per_cm": config.calibration.px_per_cm,
            "edit_region_name": config.calibration.edit_region_name,
        },
        "exit_arm_index": config.exit_arm_index,
        "rewarded_arm_index": config.rewarded_arm_index,
        "speaker_device_name": config.speaker_device_name,
        "speaker_volume_pct": config.speaker_volume_pct,
        "stimulus_frequency_hz": config.stimulus_frequency_hz,
        "stimulus_enabled": config.stimulus_enabled,
    }


def _radial_arm_task_from_dict(data: Dict[str, Any]) -> RadialArmTaskConfig:
    template_data = data.get("template", {}) if isinstance(data, dict) else {}
    calibration_data = data.get("calibration", {}) if isinstance(data, dict) else {}
    return RadialArmTaskConfig(
        template=RadialArmTemplateConfig(
            center_midedge_to_midedge_cm=float(
                template_data.get("center_midedge_to_midedge_cm", 80.0)
            ),
            arm_length_cm=float(template_data.get("arm_length_cm", 55.0)),
            arm_width_cm=float(template_data.get("arm_width_cm", 15.0)),
            arm_split_cm=float(template_data.get("arm_split_cm", 27.5)),
            hole_arm_index=int(template_data.get("hole_arm_index", 0)),
            hole_radius_cm=float(template_data.get("hole_radius_cm", 5.0)),
            hole_inset_from_arm_end_cm=float(
                template_data.get("hole_inset_from_arm_end_cm", 10.0)
            ),
        ),
        calibration=RadialArmCalibrationConfig(
            template_center_x_px=float(
                calibration_data.get("template_center_x_px", 0.0)
            ),
            template_center_y_px=float(
                calibration_data.get("template_center_y_px", 0.0)
            ),
            template_rotation_deg=float(
                calibration_data.get("template_rotation_deg", 0.0)
            ),
            px_per_cm=float(calibration_data.get("px_per_cm", 0.0)),
            edit_region_name=str(calibration_data.get("edit_region_name", "") or ""),
        ),
        exit_arm_index=int(data.get("exit_arm_index", 0)),
        rewarded_arm_index=int(data.get("rewarded_arm_index", 0)),
        speaker_device_name=str(data.get("speaker_device_name", "") or ""),
        speaker_volume_pct=float(data.get("speaker_volume_pct", 100.0)),
        stimulus_frequency_hz=float(data.get("stimulus_frequency_hz", 5000.0)),
        stimulus_enabled=bool(data.get("stimulus_enabled", False)),
    )


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
    track_backup_only: bool = False,
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
        "track_backup_only": track_backup_only,
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


def _merge_gui_into_config(
    config: AcquisitionConfig, gui: Optional[Dict[str, Any]]
) -> None:
    """Apply legacy GUI dict keys into config for backward compatibility."""
    if not gui or not isinstance(gui, dict):
        return
    if "track_sleap_path" in gui:
        config.sleap_model_path = str(gui.get("track_sleap_path") or "").strip()
    if gui.get("track_show") is not None:
        config.track_show = bool(gui["track_show"])
    if gui.get("track_async") is not None:
        config.track_async = bool(gui["track_async"])
    if gui.get("track_backup_only") is not None:
        config.track_backup_only = bool(gui["track_backup_only"])
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
    trial_idx = (
        max(0, min(int(data.get("last_trial_idx", 0)), n_trials - 1)) if n_trials else 0
    )
    slot_idx = data.get("last_slot_idx")
    if slot_idx is not None:
        slot_idx = max(0, min(int(slot_idx), total_slots)) if total_slots else 0
    return config, session_id, trial_idx, gui, slot_idx
