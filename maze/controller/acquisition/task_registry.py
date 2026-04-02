"""Task registry for shared acquisition shell composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from ...core.tasks import ARENA_TYPE_CIRCULAR, ARENA_TYPE_RADIAL_ARM
from .vast.config import ControllerConfig
from .radial_arm.config import RadialArmControllerConfig
from .radial_arm.trial_flow import RadialArmTrialController
from .vast import VastTrialController

AcquisitionMode = Literal["vast", "ram"]


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


TASK_SPECS: dict[AcquisitionMode, AcquisitionTaskSpec] = {
    "vast": AcquisitionTaskSpec(
        mode="vast",
        display_name="VAST",
        arena_type=ARENA_TYPE_CIRCULAR,
        window_title="Maze Acquisition",
        task_tab_label="VAST Task",
        exit_status_label="Exit #:",
        requires_mc_connection=True,
        config_factory=ControllerConfig,
        controller_factory=VastTrialController,
    ),
    "ram": AcquisitionTaskSpec(
        mode="ram",
        display_name="RAM",
        arena_type=ARENA_TYPE_RADIAL_ARM,
        window_title="Maze Acquisition",
        task_tab_label="RAM Task",
        exit_status_label="Exit arm:",
        requires_mc_connection=False,
        config_factory=RadialArmControllerConfig,
        controller_factory=RadialArmTrialController,
    ),
}


def get_task_spec(mode: AcquisitionMode) -> AcquisitionTaskSpec:
    """Return the registered acquisition task spec for ``mode``."""
    return TASK_SPECS[mode]
