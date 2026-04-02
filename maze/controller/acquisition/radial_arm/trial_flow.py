"""Dedicated radial-arm trial flow for RAM acquisition."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from ....core.session_slots import (
    clamp_slot_index,
    slot_for_trial_index,
    slot_to_animal_trial,
)
from ..shared_controller import build_run_button_states, normalize_run_mode_value
from .config import RadialArmControllerConfig
from .geometry import build_template_from_params, exit_hole_xyr_px


class RamTrialMode(Enum):
    CONTINUOUS = "continuous"
    ALTERNATING = "alternating"


class RamTrialState(Enum):
    IDLE = "idle"
    ITI = "iti"
    WAIT_FOR_START = "wait_for_start"
    TRIAL_RUNNING = "trial_running"
    TRIAL_SUCCESS = "trial_success"
    TRIAL_TIMEOUT = "trial_timeout"


def parse_ram_trial_mode(config: RadialArmControllerConfig) -> RamTrialMode:
    run_mode = normalize_run_mode_value(config.run_mode)
    try:
        return RamTrialMode(run_mode)
    except ValueError:
        return RamTrialMode.CONTINUOUS
@dataclass
class RamTrialStateMachine:
    config: RadialArmControllerConfig
    mode: RamTrialMode = RamTrialMode.CONTINUOUS
    session_id: str = ""
    slot_idx: int = 0
    state: RamTrialState = RamTrialState.IDLE
    iti_elapsed_s: float = 0.0
    trial_elapsed_s: float = 0.0
    exit_arm_index: int = 0
    success_override: Optional[bool] = None
    on_state_change: Optional[Callable[[RamTrialState], None]] = None

    def _total_slots(self) -> int:
        return self.config.session.num_animals * self.config.session.num_trials

    @property
    def trial_idx(self) -> int:
        _, trial_idx = slot_to_animal_trial(
            self.slot_idx,
            self.config.session.num_animals,
            self.config.session.num_trials,
            self.mode,
        )
        return trial_idx

    @property
    def animal_idx(self) -> int:
        animal_idx, _ = slot_to_animal_trial(
            self.slot_idx,
            self.config.session.num_animals,
            self.config.session.num_trials,
            self.mode,
        )
        return animal_idx

    def current_animal_id(self) -> str:
        self.config.session.ensure_animals()
        if not self.config.session.animals:
            return "1000"
        return self.config.session.animals[self.animal_idx].animal_id

    def session_key(self) -> str:
        return self.session_id if self.session_id else "-"

    def trial_key(self) -> str:
        return f"T{self.trial_idx + 1:02d}"

    def _set_state(self, new_state: RamTrialState) -> None:
        self.state = new_state
        if self.on_state_change is not None:
            self.on_state_change(new_state)

    def _sync_exit_arm(self) -> None:
        self.exit_arm_index = int(getattr(self.config.radial_arm, "exit_arm_index", 0))

    def start_iti(self) -> None:
        self.iti_elapsed_s = 0.0
        self.trial_elapsed_s = 0.0
        self.success_override = None
        self._sync_exit_arm()
        self._set_state(RamTrialState.ITI)

    def update_iti(self, dt_s: float) -> bool:
        if self.state != RamTrialState.ITI:
            return False
        self.iti_elapsed_s += dt_s
        if self.iti_elapsed_s >= self.config.session.iti_s:
            self._set_state(RamTrialState.WAIT_FOR_START)
            return True
        return False

    def begin_trial(self) -> None:
        self.trial_elapsed_s = 0.0
        self._set_state(RamTrialState.TRIAL_RUNNING)

    def update_trial(self, dt_s: float) -> Optional[RamTrialState]:
        if self.state == RamTrialState.WAIT_FOR_START:
            self.begin_trial()
            return self.state
        if self.state != RamTrialState.TRIAL_RUNNING:
            return None
        self.trial_elapsed_s += dt_s
        if self.success_override:
            self._set_state(RamTrialState.TRIAL_SUCCESS)
            return self.state
        if self.trial_elapsed_s >= self.config.session.max_trial_duration_s:
            self._set_state(RamTrialState.TRIAL_TIMEOUT)
            return self.state
        return None

    def advance_to_next_trial(self) -> bool:
        total = self._total_slots()
        if self.slot_idx >= total:
            return False
        self.slot_idx += 1
        if self.slot_idx >= total:
            self._set_state(RamTrialState.IDLE)
            return False
        self.iti_elapsed_s = 0.0
        self.trial_elapsed_s = 0.0
        self.success_override = None
        self._sync_exit_arm()
        return True

    def go_back_one_trial(self) -> bool:
        if self.slot_idx <= 0:
            return True
        self.slot_idx -= 1
        self.iti_elapsed_s = 0.0
        self.trial_elapsed_s = 0.0
        self.success_override = None
        self._sync_exit_arm()
        return True

    def manual_trial_success(self) -> None:
        if self.state != RamTrialState.TRIAL_RUNNING:
            return
        self._set_state(RamTrialState.TRIAL_SUCCESS)

    def force_idle(self) -> None:
        self._set_state(RamTrialState.IDLE)


_STATE_LABELS = {
    RamTrialState.IDLE: "Idle",
    RamTrialState.ITI: "ITI",
    RamTrialState.WAIT_FOR_START: "Ready",
    RamTrialState.TRIAL_RUNNING: "Trial",
    RamTrialState.TRIAL_SUCCESS: "Success",
    RamTrialState.TRIAL_TIMEOUT: "Timeout",
}
_CAN_START_PREV_NEXT = (
    RamTrialState.IDLE,
    RamTrialState.TRIAL_SUCCESS,
    RamTrialState.TRIAL_TIMEOUT,
)
_RUNNING_STATES = (
    RamTrialState.ITI,
    RamTrialState.WAIT_FOR_START,
    RamTrialState.TRIAL_RUNNING,
)


class RadialArmTrialController:
    """GUI-facing RAM controller with the same public surface as the shared shell expects."""

    def __init__(self, config: RadialArmControllerConfig) -> None:
        self._config = config
        self._sm: Optional[RamTrialStateMachine] = None
        self._run_active = False
        self._state_listeners: list[Callable[[RamTrialState], None]] = []

    @property
    def run_active(self) -> bool:
        return self._run_active

    def add_state_listener(self, callback: Callable[[RamTrialState], None]) -> None:
        self._state_listeners.append(callback)

    def _handle_state_change(self, state: RamTrialState) -> None:
        for callback in self._state_listeners:
            callback(state)

    def get_state_machine(self) -> Optional[RamTrialStateMachine]:
        return self._sm

    def get_session_snapshot(self) -> Optional[tuple[str, int, int]]:
        if self._sm is None:
            return None
        return self._sm.session_id, self._sm.trial_idx, self._sm.slot_idx

    def get_exit_position_px(self) -> tuple[float, float]:
        ram = self._config.radial_arm
        calibration = ram.calibration
        template = build_template_from_params(
            center_midedge_to_midedge_cm=ram.template.center_midedge_to_midedge_cm,
            arm_length_cm=ram.template.arm_length_cm,
            arm_width_cm=ram.template.arm_width_cm,
            arm_split_cm=ram.template.arm_split_cm,
            hole_arm_index=ram.template.hole_arm_index,
            hole_radius_cm=ram.template.hole_radius_cm,
            hole_inset_from_arm_end_cm=ram.template.hole_inset_from_arm_end_cm,
        )
        exit_x, exit_y, _ = exit_hole_xyr_px(
            template,
            exit_arm_index=ram.exit_arm_index,
            center_x_px=calibration.template_center_x_px,
            center_y_px=calibration.template_center_y_px,
            rotation_deg=calibration.template_rotation_deg,
            px_per_cm=calibration.px_per_cm,
        )
        return (float(exit_x), float(exit_y))

    def get_overlay_info(self) -> None:
        return None

    def set_legacy_exit_xy(self, exit_x_px: float, exit_y_px: float) -> None:
        del exit_x_px, exit_y_px

    def clear_legacy_exit_xy(self) -> None:
        return

    def set_exit_success_override(self, in_exit: Optional[bool]) -> None:
        if self._sm is not None:
            self._sm.success_override = in_exit

    def get_duty_for_position(self, x_px: float, y_px: float) -> float:
        del x_px, y_px
        return 0.0

    def is_recording_trial(self) -> bool:
        if not self._run_active or self._sm is None:
            return False
        return self._sm.state in _RUNNING_STATES

    def is_trial_running_phase(self) -> bool:
        if self._sm is None:
            return False
        return self._sm.state == RamTrialState.TRIAL_RUNNING

    def get_recording_metadata(self) -> Optional[tuple[str, str, str]]:
        if self._sm is None:
            return None
        return (
            self._sm.current_animal_id(),
            self._sm.session_key(),
            self._sm.trial_key(),
        )

    def get_trial_state_for_recording(self) -> Optional[str]:
        if self._sm is None:
            return None
        state_to_name = {
            RamTrialState.ITI: "iti",
            RamTrialState.WAIT_FOR_START: "wait",
            RamTrialState.TRIAL_RUNNING: "run",
        }
        return state_to_name.get(self._sm.state)

    def get_recording_frame_metrics(self, x_px: float, y_px: float) -> tuple[float, bool]:
        if self._sm is None:
            return (0.0, False)
        ram = self._config.radial_arm
        calibration = ram.calibration
        template = build_template_from_params(
            center_midedge_to_midedge_cm=ram.template.center_midedge_to_midedge_cm,
            arm_length_cm=ram.template.arm_length_cm,
            arm_width_cm=ram.template.arm_width_cm,
            arm_split_cm=ram.template.arm_split_cm,
            hole_arm_index=ram.template.hole_arm_index,
            hole_radius_cm=ram.template.hole_radius_cm,
            hole_inset_from_arm_end_cm=ram.template.hole_inset_from_arm_end_cm,
        )
        exit_x, exit_y, exit_radius_px = exit_hole_xyr_px(
            template,
            exit_arm_index=ram.exit_arm_index,
            center_x_px=calibration.template_center_x_px,
            center_y_px=calibration.template_center_y_px,
            rotation_deg=calibration.template_rotation_deg,
            px_per_cm=calibration.px_per_cm,
        )
        dx = float(x_px) - float(exit_x)
        dy = float(y_px) - float(exit_y)
        dist = float((dx * dx + dy * dy) ** 0.5)
        in_exit = dist <= float(exit_radius_px)
        return (dist, in_exit)

    def ensure_created(
        self,
        session_id: str,
        trial_idx: int,
        slot_idx: Optional[int] = None,
    ) -> None:
        if self._sm is not None:
            return
        mode = parse_ram_trial_mode(self._config)
        n_trials = self._config.session.num_trials
        n_animals = self._config.session.num_animals
        total = n_animals * n_trials
        if slot_idx is not None:
            initial_slot = clamp_slot_index(slot_idx, total)
        else:
            initial_slot = slot_for_trial_index(trial_idx, n_animals, n_trials, mode)
        self._sm = RamTrialStateMachine(
            config=self._config,
            mode=mode,
            session_id=session_id,
            slot_idx=initial_slot,
        )
        self._sm.on_state_change = self._handle_state_change

    def reset(
        self,
        session_id: str,
        trial_idx: int = 0,
        slot_idx: Optional[int] = None,
    ) -> None:
        self._sm = None
        self._run_active = False
        self.ensure_created(session_id, trial_idx, slot_idx=slot_idx)

    def tick(self, x_px: float, y_px: float, dt_s: float) -> None:
        del x_px, y_px
        if not self._run_active or self._sm is None:
            return
        if self._sm.state == RamTrialState.ITI:
            self._sm.update_iti(dt_s)
        else:
            self._sm.update_trial(dt_s)

    def start_run(self) -> None:
        self._run_active = True
        if self._sm is not None:
            self._sm.start_iti()

    def stop_run(self) -> None:
        self._run_active = False
        if self._sm is not None:
            self._sm.force_idle()

    def _trial_idx_for_ensure(self) -> int:
        if self._sm is None:
            return 0
        return self._sm.trial_idx

    def do_start(self, session_id: str, lookup_status: Optional[str] = None) -> str:
        del lookup_status
        self.ensure_created(session_id, self._trial_idx_for_ensure())
        if self._sm is None:
            return "Could not create RAM state machine."
        self.start_run()
        return "RAM trial started."

    def do_previous(self, session_id: str) -> str:
        self.ensure_created(session_id, self._trial_idx_for_ensure())
        if self._sm is None:
            return "Could not create RAM state machine."
        self._sm.go_back_one_trial()
        return f"Moved to {self._sm.session_key()} {self._sm.trial_key()}."

    def do_next(self, session_id: str) -> str:
        self.ensure_created(session_id, self._trial_idx_for_ensure())
        if self._sm is None:
            return "Could not create RAM state machine."
        more = self._sm.advance_to_next_trial()
        return "Next trial." if more else "Session complete."

    def do_end_trial(self) -> str:
        if self._sm is None:
            return "Start trial first."
        if self._sm.state != RamTrialState.TRIAL_RUNNING:
            return "No trial in progress."
        self._sm.manual_trial_success()
        return "RAM trial ended."

    def get_button_states(self) -> dict[str, bool]:
        return build_run_button_states(
            state=(None if self._sm is None else self._sm.state),
            run_active=self._run_active,
            can_start_prev_next_states=_CAN_START_PREV_NEXT,
            running_states=_RUNNING_STATES,
        )

    def get_status_dict(self, x_px: float, y_px: float) -> dict[str, Any]:
        del x_px, y_px
        empty = {
            "state": "-",
            "trial": "-",
            "exit": "-",
            "animal_id": "-",
            "iti": "-",
            "trial_timer": "-",
            "duty": "-",
            "session_id": "",
        }
        if self._sm is None:
            return empty
        sm = self._sm
        out: dict[str, Any] = {
            "state": _STATE_LABELS.get(sm.state, sm.state.value),
            "trial": sm.trial_key(),
            "exit": str(sm.exit_arm_index + 1),
            "animal_id": sm.current_animal_id(),
            "iti": "-",
            "trial_timer": "-",
            "duty": "-",
            "session_id": sm.session_id,
        }
        if sm.state == RamTrialState.ITI:
            out["iti"] = f"{sm.iti_elapsed_s:.1f} / {sm.config.session.iti_s:.0f}s"
        if sm.state == RamTrialState.TRIAL_RUNNING:
            out["trial_timer"] = (
                f"{sm.trial_elapsed_s:.1f} / {sm.config.session.max_trial_duration_s:.0f}s"
            )
        return out

    def apply_session_controls(self, session_id: str) -> None:
        self.reset(session_id, 0, slot_idx=0)
