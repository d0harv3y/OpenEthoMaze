from __future__ import annotations

VALID_STATES = {"idle", "iti", "wait", "run", "success", "timeout"}


def normalize_trial_state(state: str | None) -> str:
    """
    Normalize a raw trial_state string to one of the known values.
    Defaults to 'idle' for unknown/empty inputs.
    """
    if state is None:
        return "idle"
    s = state.strip().lower()
    return s if s in VALID_STATES else "idle"


def trial_state_band(state: str | None) -> str:
    """
    Map a per-frame trial_state to a coarse band:
    - iti_wait: 'iti' or 'wait'
    - run: 'run'
    - other: anything else (idle, success, timeout, unknown)
    """
    s = normalize_trial_state(state)
    if s in {"iti", "wait"}:
        return "iti_wait"
    if s == "run":
        return "run"
    return "other"
