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

from .arena import (
    exit_center_px,
    in_center_region,
    in_exit_zone,
    latin_square_exit_index,
    distance_to_exit_cm,
)
from .config import ArenaConfig, ControllerConfig


@dataclass
class OverlayInfo:
    """View model for drawing state-dependent overlay (center/edge circles, exit). From controller, not SM."""

    arena: ArenaConfig
    state: "TrialState"
    phase: Phase
    exit_x_px: float
    exit_y_px: float


class Phase(Enum):
    """Trial phase: determines stimulus and exit placement (extensible)."""
    HABITUATION = "habituation"  # record only, no stimulus (default)
    HABITUATION_TRAINING = "habituation_training"  # vibrate in edge, center=exit, constant duty
    VAST = "VAST"  # place exit, distance-based stimulus


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
            mode = TrialMode(run_mode.strip().lower())
        except ValueError:
            mode = TrialMode.CONTINUOUS
    else:
        mode = TrialMode.CONTINUOUS
    return phase, mode


def parse_phase_mode_from_config(config: ControllerConfig) -> tuple[Phase, TrialMode]:
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


def _slot_to_animal_trial(
    slot: int, num_animals: int, num_trials: int, mode: TrialMode
) -> tuple[int, int]:
    """Map slot index to (animal_idx, trial_idx). Continuous: animal does T1..Tn; alternating: animals rotate per trial."""
    total = num_animals * num_trials
    if total <= 0:
        return 0, 0
    effective = min(slot, total - 1) if slot >= total else max(0, slot)
    if mode == TrialMode.ALTERNATING:
        trial_idx = effective // num_animals
        animal_idx = effective % num_animals
    else:
        animal_idx = effective // num_trials
        trial_idx = effective % num_trials
    return animal_idx, trial_idx


@dataclass
class TrialStateMachine:
    """State machine for one session. Position is slot_idx; (animal_idx, trial_idx) derived by mode. Stimulus/exit by phase."""

    config: ControllerConfig
    phase: Phase = Phase.HABITUATION
    mode: TrialMode = TrialMode.CONTINUOUS
    # Current session (user-entered ID) and position in session (0 .. total_slots-1, or total_slots when complete)
    session_id: str = ""
    slot_idx: int = 0
    # State
    state: TrialState = TrialState.IDLE
    iti_elapsed_s: float = 0.0
    trial_elapsed_s: float = 0.0
    # True once rodent has self-initiated this trial by first leaving center (habituation / habituation_training).
    # From that point, the per-trial timer runs continuously (until slot changes) regardless of TrialState.
    trial_started_for_habituation: bool = False
    exit_x_px: float = 0.0
    exit_y_px: float = 0.0
    exit_angle_index: int = 0
    # Optional: when seed is set to the legacy sentinel, the GUI can inject
    # exit_x/exit_y so exit placement matches a legacy/original trial exactly.
    legacy_exit_x_px: Optional[float] = None
    legacy_exit_y_px: Optional[float] = None
    # Optional GUI-provided success predicate for VAST trials.
    # None -> use geometric in_exit_zone(track_xy, exit_center).
    exit_success_override: Optional[bool] = None
    # Callbacks (set by controller)
    on_state_change: Optional[Callable[[TrialState], None]] = None
    on_exit_placed: Optional[Callable[[float, float], None]] = None

    def _total_slots(self) -> int:
        return self.config.session.num_animals * self.config.session.num_trials

    @property
    def trial_idx(self) -> int:
        n_a = self.config.session.num_animals
        n_t = self.config.session.num_trials
        _, t = _slot_to_animal_trial(self.slot_idx, n_a, n_t, self.mode)
        return t

    @property
    def animal_idx(self) -> int:
        n_a = self.config.session.num_animals
        n_t = self.config.session.num_trials
        a, _ = _slot_to_animal_trial(self.slot_idx, n_a, n_t, self.mode)
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
                return "—"  # session complete
            exit_idx = latin_square_exit_index(
                self.session_id, self.trial_idx,
                self.config.exit_angles.n_angles,
                (None if self.config.session.seed == -1 else self.config.session.seed),
            )
            return f"{self.session_key()} {self.trial_key()} #{exit_idx + 1}"
        if self.state in (TrialState.TRIAL_SUCCESS, TrialState.TRIAL_TIMEOUT):
            next_slot = self.slot_idx + 1
            if next_slot >= total:
                return "—"  # session complete after this trial
            _, next_t = _slot_to_animal_trial(next_slot, n_a, n_t, self.mode)
            exit_idx = latin_square_exit_index(
                self.session_id, next_t,
                self.config.exit_angles.n_angles,
                (None if self.config.session.seed == -1 else self.config.session.seed),
            )
            return f"{self.session_key()} T{next_t + 1:02d} #{exit_idx + 1}"
        # Current trial (ITI, WAIT_NOT_CENTER, TRIAL_RUNNING)
        return f"{self.session_key()} {self.trial_key()} #{self.exit_angle_index + 1}"

    def start_iti(self) -> None:
        """Begin ITI (e.g. Start button). Resets ITI and trial timers for the current slot."""
        self.iti_elapsed_s = 0.0
        self.trial_elapsed_s = 0.0
        self.trial_started_for_habituation = False
        self._set_state(TrialState.ITI)

    def _enter_center_iti(self) -> None:
        """Enter ITI because rodent is in center (habituation_training only). Full ITI countdown; trial timer unchanged."""
        self.iti_elapsed_s = 0.0
        self._set_state(TrialState.ITI)

    def update_iti(self, dt_s: float) -> bool:
        """Update ITI; return True when ITI complete."""
        if self.state != TrialState.ITI:
            return False
        self.iti_elapsed_s += dt_s
        # For habituation / habituation_training, once a trial has been
        # self-initiated, the per-trial timer continues to run during ITI.
        if self.phase in (Phase.HABITUATION, Phase.HABITUATION_TRAINING) and self.trial_started_for_habituation:
            self.trial_elapsed_s += dt_s
        if self.iti_elapsed_s >= self.config.session.iti_s:
            self._set_state(TrialState.WAIT_NOT_CENTER)
            return True
        return False

    def check_not_center(self, x_px: float, y_px: float) -> bool:
        """Return True when rodent is not in center (can place exit)."""
        if self.state != TrialState.WAIT_NOT_CENTER:
            return False
        if not in_center_region(x_px, y_px, self.config.arena):
            if self.phase == Phase.VAST:
                self._place_exit(x_px, y_px)
            if self.phase in (Phase.HABITUATION, Phase.HABITUATION_TRAINING):
                # First self-initiation for this slot: start continuous per-trial timer.
                if not self.trial_started_for_habituation:
                    self.trial_elapsed_s = 0.0
                    self.trial_started_for_habituation = True
            else:
                # Non-habituation phases: reset per-trial timer on every trial start.
                self.trial_elapsed_s = 0.0
            self._set_state(TrialState.TRIAL_RUNNING)
            return True
        return False

    def _place_exit(self, rodent_x: float, rodent_y: float) -> None:
        seed = self.config.session.seed
        n = self.config.exit_angles.n_angles
        # Legacy mode: copy the exact original exit location.
        # This bypasses the Latin-square exit selection and uses the GUI-injected
        # exit_x/exit_y from the original legacy trial.
        if (
            seed == -1
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

        # Normal mode: compute the exit angle index from (session_id, trial_idx, seed).
        effective_seed: Optional[int] = None if seed == -1 else seed
        self.exit_angle_index = latin_square_exit_index(
            self.session_id, self.trial_idx, n, effective_seed
        )
        ex, ey = exit_center_px(
            rodent_x, rodent_y,
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
        """
        Update trial; return new state if trial ended (SUCCESS or TIMEOUT).
        """
        if self.state != TrialState.TRIAL_RUNNING:
            return None
        # Advance per-trial timer while the trial is running. For habituation /
        # habituation_training, tests expect this to be updated on every call to
        # update_trial (in addition to any time spent during ITI).
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
                in_exit = in_exit_zone(x_px, y_px, self.exit_x_px, self.exit_y_px, self.config.arena)
            if in_exit:
                self._set_state(TrialState.TRIAL_SUCCESS)
                return self.state
        return None

    def duty_for_position(self, x_px: float, y_px: float) -> float:
        """
        Single source of truth for duty %: 0 when not in WAIT_NOT_CENTER/TRIAL_RUNNING;
        otherwise position-based (config limits in stimulus.min/max_duty_pct, min_at_exit).
        """
        cfg = self.config
        # IDLE must always yield 0 duty regardless of phase or position.
        if self.state == TrialState.IDLE:
            return 0.0
        # ITI must always yield 0 duty (even in habituation_training).
        if self.state == TrialState.ITI:
            return 0.0
        # Only output duty during wait or trial run; otherwise 0 (MC off, GUI "—"),
        # except in habituation_training where we want duty for previews when waiting/running.
        if self.phase != Phase.HABITUATION_TRAINING:
            if self.state not in (TrialState.WAIT_NOT_CENTER, TrialState.TRIAL_RUNNING):
                return 0.0
        if self.state == TrialState.WAIT_NOT_CENTER and self.phase == Phase.VAST:
            return cfg.wait_not_center_duty_pct
        if self.phase == Phase.HABITUATION:
            return 0.0
        if self.phase == Phase.HABITUATION_TRAINING:
            # In habituation_training, motors should be ON for everything outside the center,
            # and only go to 0 once the animal enters the center region.
            # (This matches the observed behavior where leaving the annulus toward outside
            # the arena perimeter should not immediately disable stimulus.)
            if self.state in (TrialState.WAIT_NOT_CENTER, TrialState.TRIAL_RUNNING):
                return cfg.hab_training_duty_pct if not in_center_region(x_px, y_px, cfg.arena) else 0.0
            return 0.0
        # VAST: distance to exit; min duty at exit zone edge. Map to duty using config limits.
        # If the animal is outside the calibrated arena radius, project it back onto
        # the arena boundary so distance-to-exit continues to modulate during rearing.
        cx = cfg.arena.arena_center_x_px
        cy = cfg.arena.arena_center_y_px
        r_px = cfg.arena.radius_px
        if r_px > 0:
            d_center_px = math.hypot(x_px - cx, y_px - cy)
            if d_center_px > r_px:
                # Project onto arena circle (preserve direction).
                s = r_px / d_center_px
                x_px = cx + (x_px - cx) * s
                y_px = cy + (y_px - cy) * s

        d_cm = distance_to_exit_cm(
            x_px, y_px,
            self.exit_x_px, self.exit_y_px,
            cfg.arena.px_per_cm,
        )
        exit_r_cm = cfg.arena.exit_radius_cm
        R_cm = cfg.arena.radius_cm
        ppc = cfg.arena.px_per_cm
        # Max straight-line distance from exit-zone circle to arena boundary: along the
        # line through arena center C and exit E, farthest pair is |CE| + exit_r + R.
        # Duty uses rodent→E distance d_cm; linear span (max_d_cm − exit_r) = |CE| + R,
        # i.e. exit-zone inner reference to opposite arena rim (matches far wall).
        if ppc > 0 and R_cm > 0:
            d_ce_cm = math.hypot(
                self.exit_x_px - cx, self.exit_y_px - cy
            ) / ppc
            max_d_cm = R_cm + d_ce_cm + exit_r_cm
        else:
            max_d_cm = R_cm
        if d_cm <= exit_r_cm:
            normalized = 1.0
        elif max_d_cm <= exit_r_cm:
            normalized = 1.0
        else:
            normalized = 1.0 - (d_cm - exit_r_cm) / (max_d_cm - exit_r_cm)
            normalized = max(0.0, min(1.0, normalized))
        # normalized: 0=far, 1=at exit. Clamp to [min_duty_pct, max_duty_pct]
        s = cfg.stimulus
        if s.min_at_exit:
            duty = s.max_duty_pct + (s.min_duty_pct - s.max_duty_pct) * normalized
        else:
            duty = s.min_duty_pct + (s.max_duty_pct - s.min_duty_pct) * normalized
        return max(s.min_duty_pct, min(s.max_duty_pct, duty))

    def advance_to_next_trial(self) -> bool:
        """Advance one slot; return True if session has more trials. Session does not auto-advance (user sets session_id)."""
        total = self._total_slots()
        if self.slot_idx >= total:
            return False
        self.slot_idx += 1
        if self.slot_idx >= total:
            if self.state != TrialState.IDLE:
                self._set_state(TrialState.IDLE)
            return False
        # New slot: clear timers and self-init flag so next trial starts fresh.
        self.iti_elapsed_s = 0.0
        self.trial_elapsed_s = 0.0
        self.trial_started_for_habituation = False
        self.legacy_exit_x_px = None
        self.legacy_exit_y_px = None
        return True

    def go_back_one_trial(self) -> bool:
        """Go back one slot (for re-run or correction). When IDLE, only move slot (no ITI). Return True if moved."""
        if self.slot_idx <= 0:
            return True  # already at start
        self.slot_idx -= 1
        # Moving to a different slot: clear timers and self-init flag for that slot.
        self.iti_elapsed_s = 0.0
        self.trial_elapsed_s = 0.0
        self.trial_started_for_habituation = False
        self.legacy_exit_x_px = None
        self.legacy_exit_y_px = None
        self._sync_exit_index_to_position()
        return True

    def update_habituation_trial_timer(self, dt_s: float) -> None:
        """
        For habituation / habituation_training, ensure that once a trial has been
        self-initiated (trial_started_for_habituation=True), the per-trial timer
        continues to advance even while waiting for the rodent to leave/return to
        center between ITIs.

        The main advancement of trial_elapsed_s during ITI and TRIAL_RUNNING is
        handled directly in update_iti() and update_trial(). This helper keeps
        the timer running during WAIT_NOT_CENTER after self-init when used via
        TrialController.tick().
        """
        if (
            self.phase in (Phase.HABITUATION, Phase.HABITUATION_TRAINING)
            and self.trial_started_for_habituation
            and self.state == TrialState.WAIT_NOT_CENTER
        ):
            self.trial_elapsed_s += dt_s

    def _sync_exit_index_to_position(self) -> None:
        """Set exit_angle_index to Latin square for current (session_id, trial_idx) so Exit # display is consistent."""
        self.exit_angle_index = latin_square_exit_index(
            self.session_id,
            self.trial_idx,
            self.config.exit_angles.n_angles,
            (None if self.config.session.seed == -1 else self.config.session.seed),
        )

    def manual_trial_success(self) -> None:
        """End current trial as success (e.g. user observed rodent in exit but tracking did not)."""
        if self.state != TrialState.TRIAL_RUNNING:
            return
        self._set_state(TrialState.TRIAL_SUCCESS)

    def force_idle(self) -> None:
        """Force state to IDLE (e.g. when controller stops the run). Fires on_state_change."""
        self._set_state(TrialState.IDLE)


_STATE_LABELS = {
    TrialState.IDLE: "Idle",
    TrialState.ITI: "ITI",
    TrialState.WAIT_NOT_CENTER: "Wait exit",
    TrialState.TRIAL_RUNNING: "Trial",
    TrialState.TRIAL_SUCCESS: "Success",
    TrialState.TRIAL_TIMEOUT: "Timeout",
}

# States where Start / Previous / Next are enabled (idle or trial just ended).
_CAN_START_PREV_NEXT = (TrialState.IDLE, TrialState.TRIAL_SUCCESS, TrialState.TRIAL_TIMEOUT)
# States where Manual Success (end trial) is enabled.
_RUNNING_STATES = (TrialState.ITI, TrialState.WAIT_NOT_CENTER, TrialState.TRIAL_RUNNING)


class TrialController:
    """Holds trial state machine and run logic; GUI-agnostic.

    GUI calls tick/do_* and applies get_status_dict/get_button_states to widgets.
    Controller subscribes to SM (on_state_change) and forwards to registered listeners.
    """

    def __init__(self, config: ControllerConfig) -> None:
        self._config = config
        self._sm: Optional[TrialStateMachine] = None
        self._run_active = False
        self._state_listeners: List[Callable[[TrialState], None]] = []
        self._pending_legacy_exit_xy: Optional[Tuple[float, float]] = None
        self._pending_exit_success_override: Optional[bool] = None

    def set_legacy_exit_xy(self, exit_x_px: float, exit_y_px: float) -> None:
        """Inject legacy/original exit location for the current trial replay."""
        if self._sm is not None:
            self._sm.legacy_exit_x_px = float(exit_x_px)
            self._sm.legacy_exit_y_px = float(exit_y_px)
        self._pending_legacy_exit_xy = (float(exit_x_px), float(exit_y_px))

    def clear_legacy_exit_xy(self) -> None:
        """Clear any previously injected legacy exit location."""
        if self._sm is not None:
            self._sm.legacy_exit_x_px = None
            self._sm.legacy_exit_y_px = None
        self._pending_legacy_exit_xy = None

    def set_exit_success_override(self, in_exit: Optional[bool]) -> None:
        """Set optional VAST success predicate computed from tracking source-specific criteria."""
        if self._sm is not None:
            self._sm.exit_success_override = in_exit
        self._pending_exit_success_override = in_exit

    def get_state_machine(self) -> Optional[TrialStateMachine]:
        return self._sm

    @property
    def run_active(self) -> bool:
        return self._run_active

    def get_session_snapshot(self) -> Optional[Tuple[str, int, int]]:
        """Return (session_id, trial_idx, slot_idx) for save/load profile, or None if no SM."""
        if self._sm is None:
            return None
        return (self._sm.session_id, self._sm.trial_idx, self._sm.slot_idx)

    def get_exit_position_px(self) -> Tuple[float, float]:
        """Return (exit_x_px, exit_y_px) for current trial; (0.0, 0.0) if no SM."""
        if self._sm is None:
            return (0.0, 0.0)
        return (float(self._sm.exit_x_px), float(self._sm.exit_y_px))

    def get_overlay_info(self) -> Optional[OverlayInfo]:
        """Return overlay view model for drawing; None if no SM."""
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
        """True when run is active, SM exists, and state is ITI, WAIT_NOT_CENTER, or TRIAL_RUNNING."""
        if not self._run_active or self._sm is None:
            return False
        return self._sm.state in (
            TrialState.ITI,
            TrialState.WAIT_NOT_CENTER,
            TrialState.TRIAL_RUNNING,
        )

    def is_trial_running_phase(self) -> bool:
        """True during TRIAL_RUNNING (timed VAST phase), not during ITI/wait or whole-session idle."""
        if self._sm is None:
            return False
        return self._sm.state == TrialState.TRIAL_RUNNING

    def get_duty_for_position(self, x_px: float, y_px: float) -> float:
        """Duty % for given position; 0.0 if no SM."""
        if self._sm is None:
            return 0.0
        return self._sm.duty_for_position(x_px, y_px)

    def get_recording_metadata(self) -> Optional[Tuple[str, str, str]]:
        """Return (animal_id, session_key, trial_key) for TrialRecorder; None if no SM."""
        if self._sm is None:
            return None
        sm = self._sm
        return (sm.current_animal_id(), sm.session_key(), sm.trial_key())

    def get_trial_state_for_recording(self) -> Optional[str]:
        """Return 'iti' | 'wait' | 'run' for current state; None if no SM or not recording state."""
        if self._sm is None:
            return None
        _state_to_str = {
            TrialState.ITI: "iti",
            TrialState.WAIT_NOT_CENTER: "wait",
            TrialState.TRIAL_RUNNING: "run",
        }
        return _state_to_str.get(self._sm.state, "iti")

    def add_state_listener(self, callback: Callable[[TrialState], None]) -> None:
        """Register a callback to be notified on every trial state change. Controller subscribes to SM and forwards to listeners."""
        self._state_listeners.append(callback)

    def _handle_sm_state_change(self, new_state: TrialState) -> None:
        """Called by the state machine on transition; notifies all registered listeners."""
        for listener in self._state_listeners:
            listener(new_state)

    def ensure_created(self, session_id: str, trial_idx: int, slot_idx: Optional[int] = None) -> None:
        """Create state machine in IDLE if none exists. If slot_idx given (e.g. from profile), use it; else derive from trial_idx (animal 0)."""
        if self._sm is not None:
            return
        phase, mode = parse_phase_mode_from_config(self._config)
        n_trials = self._config.session.num_trials
        n_animals = self._config.session.num_animals
        total = n_animals * n_trials
        if slot_idx is not None:
            initial_slot = max(0, min(slot_idx, total)) if total else 0
        else:
            ti = max(0, min(trial_idx, n_trials - 1)) if n_trials else 0
            if mode == TrialMode.CONTINUOUS:
                initial_slot = min(ti, total - 1) if total else 0
            else:
                initial_slot = min(ti * n_animals, total - 1) if total else 0
        self._sm = TrialStateMachine(
            config=self._config, phase=phase, mode=mode, session_id=session_id, slot_idx=initial_slot
        )
        self._sm.on_state_change = self._handle_sm_state_change
        if self._pending_legacy_exit_xy is not None:
            self._sm.legacy_exit_x_px = self._pending_legacy_exit_xy[0]
            self._sm.legacy_exit_y_px = self._pending_legacy_exit_xy[1]
        self._sm.exit_success_override = self._pending_exit_success_override

    def reset(self, session_id: str, trial_idx: int = 0, slot_idx: Optional[int] = None) -> None:
        """Clear state machine and create a new one (e.g. after profile load). If slot_idx given, restore that position."""
        self._sm = None
        self._run_active = False
        self.ensure_created(session_id, trial_idx, slot_idx=slot_idx)

    def tick(self, x_px: float, y_px: float, dt_s: float) -> None:
        """One run-loop step: update ITI / check_not_center / update_trial. Call only when run_active."""
        if not self._run_active or self._sm is None:
            return
        sm = self._sm
        sm.update_habituation_trial_timer(dt_s)
        if sm.state == TrialState.ITI:
            sm.update_iti(dt_s)
        elif sm.state == TrialState.WAIT_NOT_CENTER:
            sm.check_not_center(x_px, y_px)
        elif sm.state == TrialState.TRIAL_RUNNING:
            sm.update_trial(x_px, y_px, dt_s)

    def start_run(self) -> None:
        """Start run (ITI); caller should start the timer. Sets run_active."""
        self._run_active = True
        if self._sm is not None:
            self._sm.start_iti()

    def stop_run(self) -> None:
        """Stop run; caller should stop the timer. Sets run_active False, state IDLE."""
        self._run_active = False
        if self._sm is not None:
            self._sm.force_idle()

    def _trial_idx_for_ensure(self) -> int:
        """Trial index to use when ensuring/creating SM (current position or 0)."""
        if self._sm is None:
            return 0
        return self._sm.trial_idx

    def do_start(self, session_id: str, lookup_status: Optional[str] = None) -> str:
        """Handle Start button. Returns status bar message."""
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
        """Handle Previous button. Returns status bar message."""
        self.ensure_created(session_id, self._trial_idx_for_ensure())
        if self._sm is None:
            return "Could not create state machine."
        self._sm.go_back_one_trial()
        if self._sm.state == TrialState.IDLE:
            return f"Moved to {self._sm.session_key()} {self._sm.trial_key()}."
        return "Went back one trial."

    def do_next(self, session_id: str) -> str:
        """Handle Next button. Returns status bar message."""
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
        """Handle Manual Success button. Returns status bar message."""
        if self._sm is None:
            return "Start trial first."
        if self._sm.state != TrialState.TRIAL_RUNNING:
            return "No trial in progress."
        self._sm.manual_trial_success()
        return "Trial ended (manual success)."

    def get_button_states(self) -> dict[str, bool]:
        """Return dict of button enabled state: start, previous, next, end_trial, stop. See docs/button_flow_state.md."""
        out: dict[str, bool] = {
            "start": True,
            "previous": True,
            "next": True,
            "end_trial": False,
            "stop": self._run_active,
        }
        if self._sm is None:
            return out
        s = self._sm.state
        out["start"] = s in _CAN_START_PREV_NEXT
        out["previous"] = s in _CAN_START_PREV_NEXT
        out["next"] = s in _CAN_START_PREV_NEXT
        out["end_trial"] = s in _RUNNING_STATES
        out["stop"] = self._run_active
        return out

    def get_status_dict(self, x_px: float, y_px: float) -> dict[str, Any]:
        """Return dict of status label values: state, trial, exit, animal_id, iti, trial_timer, duty, session_id."""
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
            exit_idx = latin_square_exit_index(
                sm.session_id, sm.trial_idx,
                sm.config.exit_angles.n_angles,
                (None if sm.config.session.seed == -1 else sm.config.session.seed),
            )
            out["exit"] = str(exit_idx + 1)
        else:
            out["exit"] = str(sm.exit_angle_index + 1)
        iti_s = sm.config.session.iti_s
        if sm.state == TrialState.ITI:
            out["iti"] = f"{sm.iti_elapsed_s:.1f} / {iti_s:.0f}s"
        max_trial = sm.config.session.max_trial_duration_s
        # Habituation / habituation_training: once self-initiated, always show per-trial timer for this slot.
        if sm.phase in (Phase.HABITUATION, Phase.HABITUATION_TRAINING) and sm.trial_started_for_habituation:
            out["trial_timer"] = f"{sm.trial_elapsed_s:.1f} / {max_trial:.0f}s"
        # Other phases: only show timer while trial is actively running.
        elif sm.state == TrialState.TRIAL_RUNNING:
            out["trial_timer"] = f"{sm.trial_elapsed_s:.1f} / {max_trial:.0f}s"
        duty = sm.duty_for_position(x_px, y_px)
        out["duty"] = "—" if duty == 0 else f"{duty:.0f} %"
        return out

    def apply_session_controls(self, session_id: str) -> None:
        """Apply updated session controls (session_id, phase, mode) by resetting to the first trial."""
        self.reset(session_id, 0, slot_idx=0)
