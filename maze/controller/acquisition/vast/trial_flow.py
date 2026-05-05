"""
Trial logic: state machine (ITI, wait for not-in-center, place exit, run trial, end on exit or timeout) and controller.

Phases: habituation, habituation_training, VAST (extensible). Modes: continuous, alternating.
- Continuous: same animal does all trials in sequence (animal1: T1..Tn, animal2: T1..Tn, ...).
- Alternating: animal rotates each trial (a1:T1, a2:T1, ..., an:T1, a1:T2, ..., an:Tn).
A single slot index (0 .. num_animals * num_trials - 1) maps to (animal_idx, trial_idx) by mode.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, List, Optional, Tuple

from ....core.session_slots import (
    clamp_slot_index,
    slot_for_trial_index,
    slot_to_animal_trial,
)
from ..region_code import REGION_OOB, VastRegionCodeTracker
from ..shared_controller import build_run_button_states, normalize_run_mode_value
from .arena import (
    distance_px,
    distance_to_exit_cm,
    exit_center_px,
    in_center_region,
    in_exit_zone,
    latin_square_exit_index,
)
from .config import ArenaConfig, VastControllerConfig


@dataclass
class OverlayInfo:
    """View model for drawing state-dependent overlay (center/edge circles, exit). From controller, not SM."""

    arena: ArenaConfig
    state: "TrialState"
    phase: "Phase"
    exit_x_px: float
    exit_y_px: float


class Phase(Enum):
    """Trial phase: determines stimulus and exit placement (extensible)."""

    HABITUATION = "habituation"
    HABITUATION_TRAINING = "habituation_training"
    VAST = "VAST"


class TrialMode(Enum):
    """Trial ordering: continuous = one animal T1..Tn then next; alternating = rotate animal each trial."""

    CONTINUOUS = "continuous"
    ALTERNATING = "alternating"


def _parse_phase_mode(
    run_phase: Optional[str] = None,
    run_mode: Optional[str] = None,
) -> tuple[Phase, TrialMode]:
    """Parse phase and mode from config run_phase and run_mode strings."""
    if run_phase is not None and run_phase.strip():
        try:
            phase = Phase(run_phase.strip())
        except ValueError:
            phase = Phase.HABITUATION
    else:
        phase = Phase.HABITUATION
    if run_mode is not None and run_mode.strip():
        try:
            mode = TrialMode(normalize_run_mode_value(run_mode))
        except ValueError:
            mode = TrialMode.CONTINUOUS
    else:
        mode = TrialMode.CONTINUOUS
    return phase, mode


def parse_phase_mode_from_config(config: VastControllerConfig) -> tuple[Phase, TrialMode]:
    """Single source of truth: parse run_phase/run_mode from config to (Phase, TrialMode)."""
    return _parse_phase_mode(
        run_phase=config.run_phase or None,
        run_mode=config.run_mode or None,
    )


class TrialState(Enum):
    IDLE = "idle"
    ITI = "iti"
    WAIT_NOT_CENTER = "wait_not_center"
    TRIAL_RUNNING = "trial_running"
    TRIAL_SUCCESS = "trial_success"
    TRIAL_TIMEOUT = "trial_timeout"


@dataclass
class TrialStateMachine:
    """State machine for one session. Position is slot_idx; (animal_idx, trial_idx) derived by mode. Stimulus/exit by phase."""

    config: VastControllerConfig
    phase: Phase = Phase.HABITUATION
    mode: TrialMode = TrialMode.CONTINUOUS
    session_id: str = ""
    slot_idx: int = 0
    state: TrialState = TrialState.IDLE
    iti_elapsed_s: float = 0.0
    trial_elapsed_s: float = 0.0
    trial_started_for_habituation: bool = False
    exit_x_px: float = 0.0
    exit_y_px: float = 0.0
    exit_angle_index: int = 0
    legacy_exit_x_px: Optional[float] = None
    legacy_exit_y_px: Optional[float] = None
    exit_success_override: Optional[bool] = None
    on_state_change: Optional[Callable[[TrialState], None]] = None
    on_exit_placed: Optional[Callable[[float, float], None]] = None

    def _total_slots(self) -> int:
        return self.config.session.num_animals * self.config.session.num_trials

    @property
    def trial_idx(self) -> int:
        n_a = self.config.session.num_animals
        n_t = self.config.session.num_trials
        _, t = slot_to_animal_trial(self.slot_idx, n_a, n_t, self.mode)
        return t

    @property
    def animal_idx(self) -> int:
        n_a = self.config.session.num_animals
        n_t = self.config.session.num_trials
        a, _ = slot_to_animal_trial(self.slot_idx, n_a, n_t, self.mode)
        return a

    def _set_state(self, new_state: TrialState) -> None:
        self.state = new_state
        if self.on_state_change:
            self.on_state_change(self.state)

    def current_animal_id(self) -> str:
        config = self.config
        config.session.ensure_animals()
        idx = self.animal_idx % len(config.session.animals)
        return config.session.animals[idx].animal_id

    def session_key(self) -> str:
        return self.session_id if self.session_id else "—"

    def trial_key(self) -> str:
        return f"T{self.trial_idx + 1:02d}"

    def _manual_exit_idx_for_slot(self, slot_idx: int) -> int:
        sess = self.config.session
        n = self.config.exit_angles.n_angles
        default_i = int(getattr(self.config.exit_angles, "default_manual_exit_index", 0))
        default_i = max(0, min(n - 1, default_i))
        raw = sess.exit_schedule_indices
        if raw is None or slot_idx < 0 or slot_idx >= len(raw):
            return default_i
        return max(0, min(n - 1, int(raw[slot_idx])))

    def _latin_preview_exit_idx(self, trial_t: int) -> int:
        return latin_square_exit_index(
            self.session_id,
            trial_t,
            self.config.exit_angles.n_angles,
            self.config.session.seed_auto_value,
        )

    def queued_trial_display(self) -> str:
        """
        Return a short string for the trial shown in the status panel: e.g. "sess1 T02 #3".
        - IDLE: trial that will run when user clicks Start (or "—" if session complete).
        - ITI / WAIT_NOT_CENTER / TRIAL_RUNNING: current trial.
        - TRIAL_SUCCESS / TRIAL_TIMEOUT: next trial (after advance).
        """
        total = self._total_slots()
        n_a = self.config.session.num_animals
        n_t = self.config.session.num_trials
        if self.state == TrialState.IDLE:
            if self.slot_idx >= total:
                return "—"
            if self.config.session.seed_mode == "manual":
                exit_idx = self._manual_exit_idx_for_slot(self.slot_idx)
            else:
                exit_idx = self._latin_preview_exit_idx(self.trial_idx)
            return f"{self.session_key()} {self.trial_key()} #{exit_idx + 1}"
        if self.state in (TrialState.TRIAL_SUCCESS, TrialState.TRIAL_TIMEOUT):
            next_slot = self.slot_idx + 1
            if next_slot >= total:
                return "—"
            _, next_t = slot_to_animal_trial(next_slot, n_a, n_t, self.mode)
            if self.config.session.seed_mode == "manual":
                exit_idx = self._manual_exit_idx_for_slot(next_slot)
            else:
                exit_idx = self._latin_preview_exit_idx(next_t)
            return f"{self.session_key()} T{next_t + 1:02d} #{exit_idx + 1}"
        return f"{self.session_key()} {self.trial_key()} #{self.exit_angle_index + 1}"

    def start_iti(self) -> None:
        self.iti_elapsed_s = 0.0
        self.trial_elapsed_s = 0.0
        self.trial_started_for_habituation = False
        self._set_state(TrialState.ITI)

    def _enter_center_iti(self) -> None:
        self.iti_elapsed_s = 0.0
        self._set_state(TrialState.ITI)

    def update_iti(self, dt_s: float) -> bool:
        if self.state != TrialState.ITI:
            return False
        self.iti_elapsed_s += dt_s
        if (
            self.phase in (Phase.HABITUATION, Phase.HABITUATION_TRAINING)
            and self.trial_started_for_habituation
        ):
            self.trial_elapsed_s += dt_s
        if self.iti_elapsed_s >= self.config.session.iti_s:
            self._set_state(TrialState.WAIT_NOT_CENTER)
            return True
        return False

    def check_not_center(self, x_px: float, y_px: float) -> bool:
        if self.state != TrialState.WAIT_NOT_CENTER:
            return False
        if not in_center_region(x_px, y_px, self.config.arena):
            if self.phase == Phase.VAST:
                self._place_exit(x_px, y_px)
            if self.phase in (Phase.HABITUATION, Phase.HABITUATION_TRAINING):
                if not self.trial_started_for_habituation:
                    self.trial_elapsed_s = 0.0
                    self.trial_started_for_habituation = True
            else:
                self.trial_elapsed_s = 0.0
            self._set_state(TrialState.TRIAL_RUNNING)
            return True
        return False

    def _place_exit(self, rodent_x: float, rodent_y: float) -> None:
        seed_mode = self.config.session.seed_mode
        seed_auto = self.config.session.seed_auto_value
        n = self.config.exit_angles.n_angles
        if (
            seed_mode == "legacy"
            and self.legacy_exit_x_px is not None
            and self.legacy_exit_y_px is not None
        ):
            ex_target = float(self.legacy_exit_x_px)
            ey_target = float(self.legacy_exit_y_px)
            best_idx = 0
            best_dist = float("inf")
            for i in range(n):
                ex_c, ey_c = exit_center_px(
                    rodent_x,
                    rodent_y,
                    i,
                    self.config.arena,
                    self.config.exit_angles,
                )
                d = math.hypot(ex_c - ex_target, ey_c - ey_target)
                if d < best_dist:
                    best_dist = d
                    best_idx = i
            self.exit_angle_index = best_idx
            self.exit_x_px = ex_target
            self.exit_y_px = ey_target
            if self.on_exit_placed:
                self.on_exit_placed(ex_target, ey_target)
            return

        if seed_mode == "manual":
            self.exit_angle_index = self._manual_exit_idx_for_slot(self.slot_idx)
            ex, ey = exit_center_px(
                rodent_x,
                rodent_y,
                self.exit_angle_index,
                self.config.arena,
                self.config.exit_angles,
            )
            self.exit_x_px, self.exit_y_px = ex, ey
            if self.on_exit_placed:
                self.on_exit_placed(ex, ey)
            return

        self.exit_angle_index = latin_square_exit_index(
            self.session_id,
            self.trial_idx,
            n,
            seed_auto,
        )
        ex, ey = exit_center_px(
            rodent_x,
            rodent_y,
            self.exit_angle_index,
            self.config.arena,
            self.config.exit_angles,
        )
        self.exit_x_px, self.exit_y_px = ex, ey
        if self.on_exit_placed:
            self.on_exit_placed(ex, ey)

    def update_trial(
        self,
        x_px: float,
        y_px: float,
        dt_s: float,
    ) -> Optional[TrialState]:
        if self.state != TrialState.TRIAL_RUNNING:
            return None
        self.trial_elapsed_s += dt_s
        max_dur = self.config.session.max_trial_duration_s
        if self.trial_elapsed_s >= max_dur:
            self._set_state(TrialState.TRIAL_TIMEOUT)
            return self.state
        if self.phase == Phase.HABITUATION_TRAINING and in_center_region(
            x_px, y_px, self.config.arena
        ):
            self._enter_center_iti()
            return self.state
        if self.phase == Phase.VAST:
            in_exit = self.exit_success_override
            if in_exit is None:
                in_exit = in_exit_zone(
                    x_px,
                    y_px,
                    self.exit_x_px,
                    self.exit_y_px,
                    self.config.arena,
                )
            if in_exit:
                self._set_state(TrialState.TRIAL_SUCCESS)
                return self.state
        return None

    def duty_for_position(self, x_px: float, y_px: float) -> float:
        cfg = self.config
        if self.state == TrialState.IDLE:
            return 0.0
        if self.state == TrialState.ITI:
            return 0.0
        if self.phase != Phase.HABITUATION_TRAINING:
            if self.state not in (TrialState.WAIT_NOT_CENTER, TrialState.TRIAL_RUNNING):
                return 0.0
        if self.state == TrialState.WAIT_NOT_CENTER and self.phase == Phase.VAST:
            return cfg.wait_not_center_duty_pct
        if self.phase == Phase.HABITUATION:
            return 0.0
        if self.phase == Phase.HABITUATION_TRAINING:
            if self.state in (TrialState.WAIT_NOT_CENTER, TrialState.TRIAL_RUNNING):
                return (
                    cfg.hab_training_duty_pct
                    if not in_center_region(x_px, y_px, cfg.arena)
                    else 0.0
                )
            return 0.0
        cx = cfg.arena.arena_center_x_px
        cy = cfg.arena.arena_center_y_px
        r_px = cfg.arena.radius_px
        if r_px > 0:
            d_center_px = math.hypot(x_px - cx, y_px - cy)
            if d_center_px > r_px:
                scale = r_px / d_center_px
                x_px = cx + (x_px - cx) * scale
                y_px = cy + (y_px - cy) * scale

        d_cm = distance_to_exit_cm(
            x_px,
            y_px,
            self.exit_x_px,
            self.exit_y_px,
            cfg.arena.px_per_cm,
        )
        exit_r_cm = cfg.arena.exit_radius_cm
        radius_cm = cfg.arena.radius_cm
        ppc = cfg.arena.px_per_cm
        if ppc > 0 and radius_cm > 0:
            d_ce_cm = math.hypot(self.exit_x_px - cx, self.exit_y_px - cy) / ppc
            max_d_cm = radius_cm + d_ce_cm + exit_r_cm
        else:
            max_d_cm = radius_cm
        if d_cm <= exit_r_cm or max_d_cm <= exit_r_cm:
            normalized = 1.0
        else:
            normalized = 1.0 - (d_cm - exit_r_cm) / (max_d_cm - exit_r_cm)
            normalized = max(0.0, min(1.0, normalized))
        stimulus = cfg.stimulus
        if stimulus.min_at_exit:
            duty = stimulus.max_duty_pct + (
                stimulus.min_duty_pct - stimulus.max_duty_pct
            ) * normalized
        else:
            duty = stimulus.min_duty_pct + (
                stimulus.max_duty_pct - stimulus.min_duty_pct
            ) * normalized
        return max(stimulus.min_duty_pct, min(stimulus.max_duty_pct, duty))

    def advance_to_next_trial(self) -> bool:
        total = self._total_slots()
        if self.slot_idx >= total:
            return False
        self.slot_idx += 1
        if self.slot_idx >= total:
            if self.state != TrialState.IDLE:
                self._set_state(TrialState.IDLE)
            return False
        self.iti_elapsed_s = 0.0
        self.trial_elapsed_s = 0.0
        self.trial_started_for_habituation = False
        self.legacy_exit_x_px = None
        self.legacy_exit_y_px = None
        return True

    def go_back_one_trial(self) -> bool:
        if self.slot_idx <= 0:
            return True
        self.slot_idx -= 1
        self.iti_elapsed_s = 0.0
        self.trial_elapsed_s = 0.0
        self.trial_started_for_habituation = False
        self.legacy_exit_x_px = None
        self.legacy_exit_y_px = None
        self._sync_exit_index_to_position()
        return True

    def update_habituation_trial_timer(self, dt_s: float) -> None:
        if (
            self.phase in (Phase.HABITUATION, Phase.HABITUATION_TRAINING)
            and self.trial_started_for_habituation
            and self.state == TrialState.WAIT_NOT_CENTER
        ):
            self.trial_elapsed_s += dt_s

    def _sync_exit_index_to_position(self) -> None:
        if self.config.session.seed_mode == "manual":
            self.exit_angle_index = self._manual_exit_idx_for_slot(self.slot_idx)
            return
        self.exit_angle_index = latin_square_exit_index(
            self.session_id,
            self.trial_idx,
            self.config.exit_angles.n_angles,
            self.config.session.seed_auto_value,
        )

    def manual_trial_success(self) -> None:
        if self.state != TrialState.TRIAL_RUNNING:
            return
        self._set_state(TrialState.TRIAL_SUCCESS)

    def force_idle(self) -> None:
        self._set_state(TrialState.IDLE)


_STATE_LABELS = {
    TrialState.IDLE: "Idle",
    TrialState.ITI: "ITI",
    TrialState.WAIT_NOT_CENTER: "Wait exit",
    TrialState.TRIAL_RUNNING: "Trial",
    TrialState.TRIAL_SUCCESS: "Success",
    TrialState.TRIAL_TIMEOUT: "Timeout",
}
_CAN_START_PREV_NEXT = (
    TrialState.IDLE,
    TrialState.TRIAL_SUCCESS,
    TrialState.TRIAL_TIMEOUT,
)
_RUNNING_STATES = (
    TrialState.ITI,
    TrialState.WAIT_NOT_CENTER,
    TrialState.TRIAL_RUNNING,
)


class TrialController:
    """Holds trial state machine and run logic; GUI-agnostic."""

    def __init__(self, config: VastControllerConfig) -> None:
        self._config = config
        self._sm: Optional[TrialStateMachine] = None
        self._run_active = False
        self._state_listeners: List[Callable[[TrialState], None]] = []
        self._pending_legacy_exit_xy: Optional[Tuple[float, float]] = None
        self._pending_exit_success_override: Optional[bool] = None
        self._region_tracker = VastRegionCodeTracker()
        self._region_trial_key: Optional[Tuple[str, int]] = None

    def set_legacy_exit_xy(self, exit_x_px: float, exit_y_px: float) -> None:
        if self._sm is not None:
            self._sm.legacy_exit_x_px = float(exit_x_px)
            self._sm.legacy_exit_y_px = float(exit_y_px)
        self._pending_legacy_exit_xy = (float(exit_x_px), float(exit_y_px))

    def clear_legacy_exit_xy(self) -> None:
        if self._sm is not None:
            self._sm.legacy_exit_x_px = None
            self._sm.legacy_exit_y_px = None
        self._pending_legacy_exit_xy = None

    def set_exit_success_override(self, in_exit: Optional[bool]) -> None:
        if self._sm is not None:
            self._sm.exit_success_override = in_exit
        self._pending_exit_success_override = in_exit

    def get_state_machine(self) -> Optional[TrialStateMachine]:
        return self._sm

    @property
    def run_active(self) -> bool:
        return self._run_active

    def get_session_snapshot(self) -> Optional[Tuple[str, int, int]]:
        if self._sm is None:
            return None
        return (self._sm.session_id, self._sm.trial_idx, self._sm.slot_idx)

    def get_exit_position_px(self) -> Tuple[float, float]:
        if self._sm is None:
            return (0.0, 0.0)
        return (float(self._sm.exit_x_px), float(self._sm.exit_y_px))

    def get_overlay_info(self) -> Optional[OverlayInfo]:
        if self._sm is None:
            return None
        sm = self._sm
        return OverlayInfo(
            arena=sm.config.arena,
            state=sm.state,
            phase=sm.phase,
            exit_x_px=sm.exit_x_px,
            exit_y_px=sm.exit_y_px,
        )

    def is_recording_trial(self) -> bool:
        if not self._run_active or self._sm is None:
            return False
        return self._sm.state in (
            TrialState.ITI,
            TrialState.WAIT_NOT_CENTER,
            TrialState.TRIAL_RUNNING,
        )

    def is_trial_running_phase(self) -> bool:
        if self._sm is None:
            return False
        return self._sm.state == TrialState.TRIAL_RUNNING

    def get_duty_for_position(self, x_px: float, y_px: float) -> float:
        if self._sm is None:
            return 0.0
        return self._sm.duty_for_position(x_px, y_px)

    def get_recording_metadata(self) -> Optional[Tuple[str, str, str]]:
        if self._sm is None:
            return None
        sm = self._sm
        return (sm.current_animal_id(), sm.session_key(), sm.trial_key())

    def get_trial_state_for_recording(self) -> Optional[str]:
        if self._sm is None:
            return None
        state_to_str = {
            TrialState.ITI: "iti",
            TrialState.WAIT_NOT_CENTER: "wait",
            TrialState.TRIAL_RUNNING: "run",
        }
        return state_to_str.get(self._sm.state, "iti")

    def get_recording_frame_metrics(self, x_px: float, y_px: float) -> tuple[float, bool]:
        if self._sm is None:
            return (0.0, False)
        exit_x_px, exit_y_px = self.get_exit_position_px()
        return (
            distance_px(x_px, y_px, exit_x_px, exit_y_px),
            in_exit_zone(x_px, y_px, exit_x_px, exit_y_px, self._config.arena),
        )

    def get_region_code_for_recording(self, x_px: float, y_px: float) -> str:
        """Per-frame VAST region label; same rules as :mod:`maze.controller.acquisition.region_code`."""
        if self._sm is None:
            return REGION_OOB
        sm = self._sm
        key = (sm.session_id, sm.slot_idx)
        if key != self._region_trial_key:
            self._region_trial_key = key
            self._region_tracker.reset()
        return self._region_tracker.update(
            float(x_px),
            float(y_px),
            arena=sm.config.arena,
            exit_angles=sm.config.exit_angles,
            assigned_exit_index=int(sm.exit_angle_index),
        )

    def add_state_listener(self, callback: Callable[[TrialState], None]) -> None:
        self._state_listeners.append(callback)

    def _handle_sm_state_change(self, new_state: TrialState) -> None:
        for listener in self._state_listeners:
            listener(new_state)

    def ensure_created(
        self,
        session_id: str,
        trial_idx: int,
        slot_idx: Optional[int] = None,
    ) -> None:
        if self._sm is not None:
            return
        phase, mode = parse_phase_mode_from_config(self._config)
        n_trials = self._config.session.num_trials
        n_animals = self._config.session.num_animals
        total = n_animals * n_trials
        if slot_idx is not None:
            initial_slot = clamp_slot_index(slot_idx, total)
        else:
            initial_slot = slot_for_trial_index(trial_idx, n_animals, n_trials, mode)
        self._sm = TrialStateMachine(
            config=self._config,
            phase=phase,
            mode=mode,
            session_id=session_id,
            slot_idx=initial_slot,
        )
        self._sm.on_state_change = self._handle_sm_state_change
        if self._pending_legacy_exit_xy is not None:
            self._sm.legacy_exit_x_px = self._pending_legacy_exit_xy[0]
            self._sm.legacy_exit_y_px = self._pending_legacy_exit_xy[1]
        self._sm.exit_success_override = self._pending_exit_success_override

    def reset(
        self,
        session_id: str,
        trial_idx: int = 0,
        slot_idx: Optional[int] = None,
    ) -> None:
        self._sm = None
        self._run_active = False
        self.ensure_created(session_id, trial_idx, slot_idx=slot_idx)

    def tick(
        self,
        x_px: float,
        y_px: float,
        dt_s: float,
        *,
        trial_clock_dt_s: Optional[float] = None,
    ) -> None:
        if not self._run_active or self._sm is None:
            return
        sm = self._sm
        sm.update_habituation_trial_timer(dt_s)
        if sm.state == TrialState.ITI:
            sm.update_iti(dt_s)
        elif sm.state == TrialState.WAIT_NOT_CENTER:
            sm.check_not_center(x_px, y_px)
        elif sm.state == TrialState.TRIAL_RUNNING:
            dt_trial = dt_s if trial_clock_dt_s is None else trial_clock_dt_s
            sm.update_trial(x_px, y_px, dt_trial)

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
        if self._sm is not None and self._run_active:
            if self._sm.state in (TrialState.TRIAL_SUCCESS, TrialState.TRIAL_TIMEOUT):
                self.stop_run()
                return "Returned to idle."
        self.ensure_created(session_id, self._trial_idx_for_ensure())
        if self._sm is None:
            return "Could not create state machine."
        self.start_run()
        if lookup_status:
            return f"Trial started. {lookup_status}"
        return "Trial started."

    def do_previous(self, session_id: str) -> str:
        self.ensure_created(session_id, self._trial_idx_for_ensure())
        if self._sm is None:
            return "Could not create state machine."
        self._sm.go_back_one_trial()
        if self._sm.state == TrialState.IDLE:
            return f"Moved to {self._sm.session_key()} {self._sm.trial_key()}."
        return "Went back one trial."

    def do_next(self, session_id: str) -> str:
        self.ensure_created(session_id, self._trial_idx_for_ensure())
        if self._sm is None:
            return "Could not create state machine."
        sm = self._sm
        if sm.state in (TrialState.TRIAL_SUCCESS, TrialState.TRIAL_TIMEOUT):
            more = sm.advance_to_next_trial()
            return "Next trial." if more else "Session complete."
        if sm.state == TrialState.IDLE:
            more = sm.advance_to_next_trial()
            if more:
                return f"Moved to {sm.session_key()} {sm.trial_key()}."
            return "Session complete (end of sessions)."
        if sm.state == TrialState.WAIT_NOT_CENTER:
            return "Trial starts when rodent leaves center."
        return "Wait for ITI or trial end."

    def do_end_trial(self) -> str:
        if self._sm is None:
            return "Start trial first."
        if self._sm.state != TrialState.TRIAL_RUNNING:
            return "No trial in progress."
        self._sm.manual_trial_success()
        return "Trial ended (manual success)."

    def get_button_states(self) -> dict[str, bool]:
        return build_run_button_states(
            state=(None if self._sm is None else self._sm.state),
            run_active=self._run_active,
            can_start_prev_next_states=_CAN_START_PREV_NEXT,
            running_states=_RUNNING_STATES,
        )

    def get_status_dict(self, x_px: float, y_px: float) -> dict[str, Any]:
        empty = {
            "state": "—",
            "trial": "—",
            "exit": "—",
            "animal_id": "—",
            "iti": "—",
            "trial_timer": "—",
            "duty": "—",
            "session_id": "",
        }
        if self._sm is None:
            return empty
        sm = self._sm
        out: dict[str, Any] = {
            "state": _STATE_LABELS.get(sm.state, sm.state.value),
            "trial": sm.trial_key(),
            "exit": "",
            "animal_id": sm.current_animal_id(),
            "iti": "—",
            "trial_timer": "—",
            "duty": "—",
            "session_id": sm.session_id,
        }
        if sm.state in (TrialState.IDLE, TrialState.ITI, TrialState.WAIT_NOT_CENTER):
            if sm.config.session.seed_mode == "manual":
                exit_idx = sm._manual_exit_idx_for_slot(sm.slot_idx)
            else:
                exit_idx = latin_square_exit_index(
                    sm.session_id,
                    sm.trial_idx,
                    sm.config.exit_angles.n_angles,
                    sm.config.session.seed_auto_value,
                )
            out["exit"] = str(exit_idx + 1)
        else:
            out["exit"] = str(sm.exit_angle_index + 1)
        iti_s = sm.config.session.iti_s
        if sm.state == TrialState.ITI:
            out["iti"] = f"{sm.iti_elapsed_s:.1f} / {iti_s:.0f}s"
        max_trial = sm.config.session.max_trial_duration_s
        if (
            sm.phase in (Phase.HABITUATION, Phase.HABITUATION_TRAINING)
            and sm.trial_started_for_habituation
        ):
            out["trial_timer"] = f"{sm.trial_elapsed_s:.1f} / {max_trial:.0f}s"
        elif sm.state == TrialState.TRIAL_RUNNING:
            out["trial_timer"] = f"{sm.trial_elapsed_s:.1f} / {max_trial:.0f}s"
        duty = sm.duty_for_position(x_px, y_px)
        out["duty"] = "—" if duty == 0 else f"{duty:.0f} %"
        return out

    def apply_session_controls(self, session_id: str) -> None:
        self.reset(session_id, 0, slot_idx=0)
