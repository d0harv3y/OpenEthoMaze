from __future__ import annotations

VALID_STATES = {"idle", "iti", "wait", "run", "success", "timeout"}

# Coarse band labels written to live xy/feedback tables.
BAND_RUN = "run"
BAND_WAIT = "wait"
# Legacy band string still present on unre-processed H5.
BAND_WAIT_LEGACY = "iti_wait"


def normalize_trial_state(state: str | None) -> str:
    """
    Normalize a raw trial_state string to one of the known values.
    Defaults to 'idle' for unknown/empty inputs.
    """
    if state is None:
        return "idle"
    s = state.strip().lower()
    if s == BAND_WAIT_LEGACY:
        return "wait"
    return s if s in VALID_STATES else "idle"


def trial_state_band(state: str | None) -> str:
    """
    Map a per-frame trial_state to a coarse band:
    - wait: 'iti', 'wait', or legacy 'iti_wait'
    - run: 'run'
    - other: anything else (idle, success, timeout, unknown)
    """
    raw = (state or "").strip().lower()
    if raw == BAND_WAIT_LEGACY:
        return BAND_WAIT
    s = normalize_trial_state(state)
    if s in {"iti", "wait"}:
        return BAND_WAIT
    if s == "run":
        return BAND_RUN
    return "other"


def is_wait_band(state: str | None) -> bool:
    """True if *state* is the wait band (live ``wait`` or legacy ``iti_wait``)."""
    return trial_state_band(state) == BAND_WAIT
