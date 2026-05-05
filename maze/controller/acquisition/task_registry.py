"""Task registry for shared acquisition shell composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

from ...core.tasks import ARENA_TYPE_CIRCULAR, ARENA_TYPE_RADIAL_ARM
from .shared_controller import normalize_run_mode_value
from .shared_config import AcquisitionConfig
from .radial_arm.config import RadialArmControllerConfig
from .vast.config import VastControllerConfig

AcquisitionMode = Literal["vast", "ram"]
SessionOption = tuple[str, str]


def _get_run_mode(config: AcquisitionConfig) -> str:
    return normalize_run_mode_value(config.run_mode)


def _set_run_mode(config: AcquisitionConfig, value: str) -> None:
    config.run_mode = normalize_run_mode_value(value)


def _get_vast_phase(config: VastControllerConfig) -> str:
    return str(config.run_phase or "habituation").strip() or "habituation"


def _set_vast_phase(config: VastControllerConfig, value: str) -> None:
    config.run_phase = str(value or "habituation").strip() or "habituation"


def _get_ram_phase(config: RadialArmControllerConfig) -> str:
    return str(config.run_phase or "radial_arm").strip() or "radial_arm"


def _set_ram_phase(config: RadialArmControllerConfig, value: str) -> None:
    v = str(value or "radial_arm").strip() or "radial_arm"
    if v not in {"habituation", "radial_arm"}:
        v = "radial_arm"
    config.run_phase = v


def _build_vast_controller(config: Any) -> Any:
    from .vast import VastTrialController

    return VastTrialController(config)


def _build_ram_controller(config: Any) -> Any:
    from .radial_arm.trial_flow import RadialArmTrialController

    return RadialArmTrialController(config)


@dataclass(frozen=True)
class AcquisitionTaskSpec:
    """Task-specific composition data for the shared acquisition GUI."""

    mode: AcquisitionMode
    display_name: str
    arena_type: str
    window_title: str
    task_tab_label: str
    exit_status_label: str
    requires_mc_connection: bool
    config_factory: Callable[[], Any]
    controller_factory: Callable[[Any], Any]
    phase_label: Optional[str]
    phase_options: tuple[SessionOption, ...]
    mode_options: tuple[SessionOption, ...]
    get_phase_value: Callable[[Any], Optional[str]]
    set_phase_value: Optional[Callable[[Any, str], None]]
    get_mode_value: Callable[[Any], str]
    set_mode_value: Callable[[Any, str], None]
    get_num_exits: Callable[[Any], int]
    get_default_exit_index: Callable[[Any], int]


TASK_SPECS: dict[AcquisitionMode, AcquisitionTaskSpec] = {
    "vast": AcquisitionTaskSpec(
        mode="vast",
        display_name="VAST",
        arena_type=ARENA_TYPE_CIRCULAR,
        window_title="Maze Acquisition",
        task_tab_label="VAST Task",
        exit_status_label="Exit index (1-based):",
        requires_mc_connection=True,
        config_factory=VastControllerConfig,
        controller_factory=_build_vast_controller,
        phase_label="Phase:",
        phase_options=(
            ("Habituation", "habituation"),
            ("Habituation Training", "habituation_training"),
            ("VAST", "VAST"),
        ),
        mode_options=(
            ("Continuous", "continuous"),
            ("Alternating", "alternating"),
        ),
        get_phase_value=_get_vast_phase,
        set_phase_value=_set_vast_phase,
        get_mode_value=_get_run_mode,
        set_mode_value=_set_run_mode,
        get_num_exits=lambda config: max(1, int(config.exit_angles.n_angles)),
        get_default_exit_index=lambda config: max(
            0, min(max(1, int(config.exit_angles.n_angles)) - 1, int(config.exit_angles.default_manual_exit_index))
        ),
    ),
    "ram": AcquisitionTaskSpec(
        mode="ram",
        display_name="RAM",
        arena_type=ARENA_TYPE_RADIAL_ARM,
        window_title="Maze Acquisition",
        task_tab_label="RAM Task",
        exit_status_label="Exit index (1-based):",
        requires_mc_connection=False,
        config_factory=RadialArmControllerConfig,
        controller_factory=_build_ram_controller,
        phase_label="Phase:",
        phase_options=(
            ("Habituation", "habituation"),
            ("RAM", "radial_arm"),
        ),
        mode_options=(
            ("Continuous", "continuous"),
            ("Alternating", "alternating"),
        ),
        get_phase_value=_get_ram_phase,
        set_phase_value=_set_ram_phase,
        get_mode_value=_get_run_mode,
        set_mode_value=_set_run_mode,
        get_num_exits=lambda config: 8,
        get_default_exit_index=lambda config: max(0, min(7, int(config.radial_arm.exit_arm_index))),
    ),
}


def get_task_spec(mode: AcquisitionMode) -> AcquisitionTaskSpec:
    """Return the registered acquisition task spec for ``mode``."""
    return TASK_SPECS[mode]
