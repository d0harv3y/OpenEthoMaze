from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .gui.identity import parse_virtual_video_identity, sanitize_session_id
from .shared_config import AcquisitionConfig
from .radial_arm.config import RadialArmControllerConfig
from .radial_arm.legacy_template import apply_legacy_template_config
from ...pipeline.db import TrialKey, read_radial_arm_trial_settings, read_trial_settings
from ...pipeline.sources.legacy_ehram import find_trial_ns_row, normalize_legacy_ram_session


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRIAL_NS_PATH = PROJECT_ROOT / "inputs" / "trial_ns.csv"


@dataclass(frozen=True)
class PlaybackHydration:
    """Resolved playback identity and task parameters for a virtual video."""

    source: str
    animal_id: str
    session_id: str
    display_session_id: str
    trial_label: str
    trial_idx: int
    slot_idx: int
    status: str
    legacy_exit_xy: tuple[float, float] | None = None
    db_path: Path | None = None


def _apply_loaded_identity(
    config: AcquisitionConfig,
    *,
    animal_id: str,
    num_trials: int,
) -> None:
    config.session.num_animals = 1
    config.session.num_trials = max(1, int(num_trials))
    config.session.ensure_animals()
    config.session.animals[0].animal_id = str(animal_id)


def _parse_trial_index(trial_label: str) -> int:
    text = str(trial_label or "").strip().upper()
    if text.startswith("T") and text[1:].isdigit():
        return max(0, int(text[1:]) - 1)
    if text.isdigit():
        return max(0, int(text) - 1)
    return 0


def _candidate_h5_paths(video_path: Path, config: AcquisitionConfig) -> list[Path]:
    h5_name = (config.h5_filename or "trials.h5").strip() or "trials.h5"
    parents = [video_path.parent.parent, video_path.parent]
    candidates: list[Path] = []
    seen: set[Path] = set()
    for parent in parents:
        if not parent.exists():
            continue
        for candidate in [parent / h5_name, parent / "trials.h5", *sorted(parent.glob("*.h5"))]:
            if candidate.exists() and candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)
    explicit_legacy_db = (config.session.legacy_seed_db_path or "").strip()
    if explicit_legacy_db:
        legacy_path = Path(explicit_legacy_db)
        if legacy_path.exists() and legacy_path not in seen:
            candidates.insert(0, legacy_path)
    return candidates


def _hydrate_from_modern_db(
    video_path: Path,
    *,
    task_mode: str,
    config: AcquisitionConfig,
) -> Optional[PlaybackHydration]:
    parsed = parse_virtual_video_identity(video_path.stem)
    if parsed is None:
        return None

    animal_id, session_id, trial_label = parsed
    trial_idx = _parse_trial_index(trial_label)
    key = TrialKey(animal_id=animal_id, session=session_id, trial=trial_label)

    for db_path in _candidate_h5_paths(video_path, config):
        try:
            legacy_exit_xy: tuple[float, float] | None = None
            settings, _, _ = read_trial_settings(db_path, key)
            if settings.exit_pos is not None:
                legacy_exit_xy = (
                    float(settings.exit_pos[0]),
                    float(settings.exit_pos[1]),
                )
            if task_mode == "ram" and isinstance(config, RadialArmControllerConfig):
                payload = read_radial_arm_trial_settings(db_path, key)
                if not payload:
                    continue
                geometry_payload = payload.get("geometry_payload", {})
                template_params = geometry_payload.get("template_params", {})
                calibration = geometry_payload.get("calibration", {})
                task_attrs = payload.get("task_attrs", {})
                ram = config.radial_arm
                if template_params:
                    ram.template.center_midedge_to_midedge_cm = float(
                        template_params.get("center_midedge_to_midedge_cm", ram.template.center_midedge_to_midedge_cm)
                    )
                    ram.template.arm_length_cm = float(
                        template_params.get("arm_length_cm", ram.template.arm_length_cm)
                    )
                    ram.template.arm_width_cm = float(
                        template_params.get("arm_width_cm", ram.template.arm_width_cm)
                    )
                    ram.template.arm_split_cm = float(
                        template_params.get("arm_split_cm", ram.template.arm_split_cm)
                    )
                    ram.template.hole_arm_index = int(
                        template_params.get("hole_arm_index", ram.template.hole_arm_index)
                    )
                    ram.template.hole_radius_cm = float(
                        template_params.get("hole_radius_cm", ram.template.hole_radius_cm)
                    )
                    ram.template.hole_inset_from_arm_end_cm = float(
                        template_params.get(
                            "hole_inset_from_arm_end_cm",
                            ram.template.hole_inset_from_arm_end_cm,
                        )
                    )
                if calibration:
                    ram.calibration.template_center_x_px = float(
                        calibration.get(
                            "template_center_x_px",
                            ram.calibration.template_center_x_px,
                        )
                    )
                    ram.calibration.template_center_y_px = float(
                        calibration.get(
                            "template_center_y_px",
                            ram.calibration.template_center_y_px,
                        )
                    )
                    ram.calibration.template_rotation_deg = float(
                        calibration.get(
                            "template_rotation_deg",
                            ram.calibration.template_rotation_deg,
                        )
                    )
                    ram.calibration.px_per_cm = float(
                        calibration.get("px_per_cm", ram.calibration.px_per_cm)
                    )
                    ram.calibration.edit_region_name = str(
                        calibration.get(
                            "edit_region_name",
                            ram.calibration.edit_region_name,
                        )
                    )
                ram.exit_arm_index = int(
                    task_attrs.get("exit_arm_index", payload["trial_attrs"].get("exit_arm_index", ram.exit_arm_index))
                )
                ram.rewarded_arm_index = int(
                    task_attrs.get(
                        "rewarded_arm_index",
                        payload["trial_attrs"].get(
                            "rewarded_arm_index", ram.rewarded_arm_index
                        ),
                    )
                )
            _apply_loaded_identity(config, animal_id=animal_id, num_trials=trial_idx + 1)
            return PlaybackHydration(
                source="modern_db",
                animal_id=animal_id,
                session_id=session_id,
                display_session_id=session_id,
                trial_label=trial_label,
                trial_idx=trial_idx,
                slot_idx=trial_idx,
                status=f"Playback hydrated from {db_path.name}: {animal_id} {session_id} {trial_label}.",
                legacy_exit_xy=legacy_exit_xy,
                db_path=db_path,
            )
        except Exception:
            continue
    return None


def _hydrate_ram_from_sidecar(
    video_path: Path,
    *,
    config: RadialArmControllerConfig,
) -> Optional[PlaybackHydration]:
    row = find_trial_ns_row(video_path, DEFAULT_TRIAL_NS_PATH)
    if row is None:
        return None

    apply_legacy_template_config(config)
    config.radial_arm.exit_arm_index = int(row.escape_arm)
    config.radial_arm.rewarded_arm_index = int(row.escape_arm)
    _apply_loaded_identity(config, animal_id=row.animal_id, num_trials=max(1, _parse_trial_index(row.trial_key) + 1))
    if row.tx:
        config.session.animals[0].tx = row.tx
    if row.sex:
        config.session.animals[0].sex = row.sex

    session_id = sanitize_session_id(normalize_legacy_ram_session(row.phase))
    return PlaybackHydration(
        source="legacy_trial_ns",
        animal_id=row.animal_id,
        session_id=session_id,
        display_session_id=row.phase,
        trial_label=row.trial_key,
        trial_idx=_parse_trial_index(row.trial_key),
        slot_idx=_parse_trial_index(row.trial_key),
        status=(
            f"Playback hydrated from trial_ns.csv: {row.animal_id} {row.phase} "
            f"{row.trial_key} exit arm {row.escape_arm + 1}."
        ),
    )


def load_playback_hydration(
    video_path: Path | str,
    *,
    task_mode: str,
    config: AcquisitionConfig,
) -> Optional[PlaybackHydration]:
    """Resolve playback identity and task params for one virtual video."""
    path = Path(video_path)
    modern = _hydrate_from_modern_db(path, task_mode=task_mode, config=config)
    if modern is not None:
        return modern
    if task_mode == "ram" and isinstance(config, RadialArmControllerConfig):
        return _hydrate_ram_from_sidecar(path, config=config)
    return None
