"""
Profile save/load: calibration and user settings to/from file for easy swapping.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import (
    ArenaConfig,
    ControllerConfig,
    ExitAngleConfig,
    FallbackTrackingConfig,
    FT_TO_CM,
    SessionConfig,
    StimulusConfig,
    AnimalInfo,
)


def _arena_to_dict(c: ArenaConfig) -> Dict[str, Any]:
    return {
        "diameter_cm": c.diameter_cm,
        "diameter_display_unit": c.diameter_display_unit,
        "radius_px": c.radius_px,
        "tracking_radius_px": c.tracking_radius_px,
        "center_pct": c.center_pct,
        "exit_radius_cm": c.exit_radius_cm,
        "arena_center_x_px": c.arena_center_x_px,
        "arena_center_y_px": c.arena_center_y_px,
    }


def _arena_from_dict(d: Dict[str, Any]) -> ArenaConfig:
    # Backward compat: old profiles have diameter_ft and/or px_per_cm
    diameter_cm = d.get("diameter_cm")
    if diameter_cm is None:
        diameter_cm = float(d.get("diameter_ft", 4.0)) * FT_TO_CM
    else:
        diameter_cm = float(diameter_cm)
    radius_px = d.get("radius_px")
    if radius_px is None and "px_per_cm" in d:
        radius_px = (diameter_cm / 2.0) * float(d["px_per_cm"])
    if radius_px is not None:
        radius_px = float(radius_px)
    else:
        radius_px = 0.0
    tracking_radius_px = d.get("tracking_radius_px")
    if tracking_radius_px is not None:
        tracking_radius_px = float(tracking_radius_px)
    else:
        tracking_radius_px = 0.0
    return ArenaConfig(
        diameter_cm=diameter_cm,
        diameter_display_unit=str(d.get("diameter_display_unit", "ft")),
        radius_px=radius_px,
        tracking_radius_px=tracking_radius_px,
        center_pct=float(d.get("center_pct", 0.5)),
        exit_radius_cm=float(d.get("exit_radius_cm", 5.0)),
        arena_center_x_px=float(d.get("arena_center_x_px", 0.0)),
        arena_center_y_px=float(d.get("arena_center_y_px", 0.0)),
    )


def _exit_angles_to_dict(c: ExitAngleConfig) -> Dict[str, Any]:
    return {
        "n_angles": c.n_angles,
        "offset_deg": c.offset_deg,
        "step_deg": c.step_deg,
    }


def _exit_angles_from_dict(d: Dict[str, Any]) -> ExitAngleConfig:
    return ExitAngleConfig(
        n_angles=int(d.get("n_angles", 4)),
        offset_deg=float(d.get("offset_deg", -30.0)),
        step_deg=float(d.get("step_deg", 20.0)),
    )


def _stimulus_to_dict(c: StimulusConfig) -> Dict[str, Any]:
    return {
        "min_at_exit": c.min_at_exit,
        "min_duty_pct": c.min_duty_pct,
        "max_duty_pct": c.max_duty_pct,
    }


def _stimulus_from_dict(d: Dict[str, Any]) -> StimulusConfig:
    return StimulusConfig(
        min_at_exit=bool(d.get("min_at_exit", True)),
        min_duty_pct=float(d.get("min_duty_pct", 35.0)),
        max_duty_pct=float(d.get("max_duty_pct", 85.0)),
    )


def _animal_to_dict(a: AnimalInfo) -> Dict[str, Any]:
    return {
        "animal_id": a.animal_id,
        "tx": a.tx,
        "strain": a.strain,
        "sex": a.sex,
        "drug": a.drug,
        "notes": a.notes,
    }


def _animal_from_dict(d: Dict[str, Any]) -> AnimalInfo:
    return AnimalInfo(
        animal_id=str(d.get("animal_id", "")),
        tx=d.get("tx"),
        strain=d.get("strain"),
        sex=d.get("sex"),
        drug=d.get("drug"),
        notes=d.get("notes"),
    )


def _session_to_dict(c: SessionConfig) -> Dict[str, Any]:
    return {
        "num_animals": c.num_animals,
        "num_trials": c.num_trials,
        "max_trial_duration_s": c.max_trial_duration_s,
        "iti_s": c.iti_s,
        "seed": c.seed,
        "legacy_seed_db_path": c.legacy_seed_db_path,
        "animals": [_animal_to_dict(a) for a in c.animals],
    }


def _session_from_dict(d: Dict[str, Any]) -> SessionConfig:
    animals = [_animal_from_dict(x) for x in d.get("animals", [])]
    return SessionConfig(
        num_animals=int(d.get("num_animals", 1)),
        num_trials=int(d.get("num_trials", 9)),
        max_trial_duration_s=float(d.get("max_trial_duration_s", 300.0)),
        iti_s=float(d.get("iti_s", 30.0)),
        seed=d.get("seed"),
        legacy_seed_db_path=d.get("legacy_seed_db_path"),
        animals=animals,
    )


def _fallback_tracking_to_dict(c: "FallbackTrackingConfig") -> Dict[str, Any]:
    return {
        "min_area": c.min_area,
        "max_area": c.max_area,
        "morph_kernel_size": c.morph_kernel_size,
        "max_jump_px": c.max_jump_px,
        "selection_mode": c.selection_mode,
        "min_circularity": c.min_circularity,
        "range_low": c.range_low,
        "range_high": c.range_high,
        "node_max_jump_px": c.node_max_jump_px,
        "min_sleap_nodes": c.min_sleap_nodes,
        "show_blob_overlay": c.show_blob_overlay,
        "max_contours": c.max_contours,
    }


def _fallback_tracking_from_dict(d: Dict[str, Any]) -> "FallbackTrackingConfig":
    return FallbackTrackingConfig(
        min_area=int(d.get("min_area", 80)),
        max_area=int(d.get("max_area", 0)),
        morph_kernel_size=int(d.get("morph_kernel_size", 5)),
        max_jump_px=float(d.get("max_jump_px", 0.0)),
        selection_mode=str(d.get("selection_mode", "closest_else_largest")),
        min_circularity=float(d.get("min_circularity", 0.0)),
        range_low=int(d.get("range_low", 0)),
        range_high=int(d.get("range_high", 255)),
        node_max_jump_px=float(d.get("node_max_jump_px", 0.0)),
        min_sleap_nodes=int(d.get("min_sleap_nodes", 1)),
        show_blob_overlay=bool(d.get("show_blob_overlay", True)),
        max_contours=int(d.get("max_contours", 0)),
    )


def config_to_dict(config: ControllerConfig) -> Dict[str, Any]:
    return {
        "arena": _arena_to_dict(config.arena),
        "exit_angles": _exit_angles_to_dict(config.exit_angles),
        "stimulus": _stimulus_to_dict(config.stimulus),
        "session": _session_to_dict(config.session),
        "hab_training_duty_pct": config.hab_training_duty_pct,
        "wait_not_center_duty_pct": config.wait_not_center_duty_pct,
        "output_dir": str(config.output_dir) if config.output_dir else None,
        "h5_filename": config.h5_filename,
        "run_phase": config.run_phase,
        "run_mode": config.run_mode,
        "run_analysis_after_trial": config.run_analysis_after_trial,
        "fallback_tracking": _fallback_tracking_to_dict(config.fallback_tracking),
        "sleap_confidence_pct": config.sleap_confidence_pct,
        "sleap_every_n": config.sleap_every_n,
        "sleap_exit_min_keypoints": config.sleap_exit_min_keypoints,
        "fallback_exit_blob_overlap_pct": config.fallback_exit_blob_overlap_pct,
        "sleap_model_path": config.sleap_model_path or "",
        "track_show": config.track_show,
        "track_async": config.track_async,
        "track_backup_only": config.track_backup_only,
        "overlay_opacity_pct": config.overlay_opacity_pct,
        "arduino_port": config.arduino_port,
        "schema_version": 1,
    }


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


def gui_from_dict(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return gui dict for applying to UI; None if missing or empty."""
    if not d or not isinstance(d, dict):
        return None
    return d


def _run_phase_from_dict(d: Dict[str, Any]) -> str:
    """Extract run_phase from profile dict."""
    return str(d.get("run_phase", "habituation") or "habituation").strip() or "habituation"


def _run_mode_from_dict(d: Dict[str, Any]) -> str:
    """Extract run_mode (continuous|alternating) from profile dict."""
    val = str(d.get("run_mode", "continuous") or "continuous").strip().lower()
    return val if val in ("continuous", "alternating") else "continuous"


def config_from_dict(d: Dict[str, Any]) -> ControllerConfig:
    out_dir = d.get("output_dir")
    return ControllerConfig(
        arena=_arena_from_dict(d.get("arena", {})),
        exit_angles=_exit_angles_from_dict(d.get("exit_angles", {})),
        stimulus=_stimulus_from_dict(d.get("stimulus", {})),
        session=_session_from_dict(d.get("session", {})),
        hab_training_duty_pct=float(d.get("hab_training_duty_pct", 60.0)),
        wait_not_center_duty_pct=float(d.get("wait_not_center_duty_pct", 0.0)),
        output_dir=out_dir if out_dir else None,
        h5_filename=str(d.get("h5_filename", "trials.h5") or "trials.h5").strip() or "trials.h5",
        run_phase=_run_phase_from_dict(d),
        run_mode=_run_mode_from_dict(d),
        run_analysis_after_trial=bool(d.get("run_analysis_after_trial", False)),
        fallback_tracking=_fallback_tracking_from_dict(d.get("fallback_tracking", {})),
        sleap_confidence_pct=int(d.get("sleap_confidence_pct", 50)),
        sleap_every_n=max(1, min(5, int(d.get("sleap_every_n", 1)))),
        sleap_exit_min_keypoints=max(1, int(d.get("sleap_exit_min_keypoints", 2))),
        fallback_exit_blob_overlap_pct=max(0.0, min(100.0, float(d.get("fallback_exit_blob_overlap_pct", 15.0)))),
        sleap_model_path=str(d.get("sleap_model_path", "") or "").strip(),
        track_show=bool(d.get("track_show", True)),
        track_async=bool(d.get("track_async", False)),
        track_backup_only=bool(d.get("track_backup_only", False)),
        overlay_opacity_pct=max(0, min(100, int(d.get("overlay_opacity_pct", 70)))),
        arduino_port=d.get("arduino_port") or None,
    )


def save_profile(
    config: ControllerConfig,
    path: Path,
    *,
    session_id: Optional[str] = None,
    trial_idx: Optional[int] = None,
    slot_idx: Optional[int] = None,
    gui: Optional[Dict[str, Any]] = None,
) -> None:
    """Write profile to JSON file. Optionally include last session ID, trial index, slot index, and GUI settings."""
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _merge_gui_into_config(config: ControllerConfig, gui: Optional[Dict[str, Any]]) -> None:
    """Apply legacy gui dict keys into config for backward compatibility."""
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


def load_profile(path: Path) -> Tuple[ControllerConfig, str, int, Optional[Dict[str, Any]], Optional[int]]:
    """Load profile from JSON file. Returns (config, last_session_id, last_trial_idx, gui_dict or None, last_slot_idx or None)."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    config = config_from_dict(d)
    gui = gui_from_dict(d.get("gui"))
    _merge_gui_into_config(config, gui)
    n_trials = config.session.num_trials
    n_animals = config.session.num_animals
    total_slots = n_animals * n_trials
    # Backward compat: old profiles have last_session_idx (int)
    last_session_id = d.get("last_session_id")
    if last_session_id is None and "last_session_idx" in d:
        last_session_id = f"S{int(d['last_session_idx']) + 1:02d}"
    if last_session_id is None:
        last_session_id = ""
    session_id = str(last_session_id) if last_session_id else ""
    trial_idx = max(0, min(int(d.get("last_trial_idx", 0)), n_trials - 1)) if n_trials else 0
    slot_idx = d.get("last_slot_idx")
    if slot_idx is not None:
        slot_idx = max(0, min(int(slot_idx), total_slots)) if total_slots else 0
    return config, session_id, trial_idx, gui, slot_idx
