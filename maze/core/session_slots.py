"""Shared helpers for mapping session slots to animals and trials."""

from __future__ import annotations

from enum import Enum


def _normalize_mode(mode: str | Enum) -> str:
    value = mode.value if isinstance(mode, Enum) else mode
    return str(value).strip().lower()


def clamp_slot_index(slot: int, total_slots: int) -> int:
    """Clamp a slot index into the valid session range."""
    if total_slots <= 0:
        return 0
    return max(0, min(int(slot), total_slots - 1))


def slot_to_animal_trial(
    slot: int,
    num_animals: int,
    num_trials: int,
    mode: str | Enum,
) -> tuple[int, int]:
    """Map a flat session slot index to ``(animal_idx, trial_idx)``."""
    total = num_animals * num_trials
    if total <= 0:
        return 0, 0
    effective = clamp_slot_index(slot, total)
    if _normalize_mode(mode) == "alternating":
        trial_idx = effective // num_animals
        animal_idx = effective % num_animals
    else:
        animal_idx = effective // num_trials
        trial_idx = effective % num_trials
    return animal_idx, trial_idx


def slot_for_trial_index(
    trial_idx: int,
    num_animals: int,
    num_trials: int,
    mode: str | Enum,
) -> int:
    """Return the first slot corresponding to the requested trial index."""
    total = num_animals * num_trials
    if total <= 0 or num_trials <= 0:
        return 0
    clamped_trial = max(0, min(int(trial_idx), num_trials - 1))
    if _normalize_mode(mode) == "alternating":
        slot = clamped_trial * num_animals
    else:
        slot = clamped_trial
    return clamp_slot_index(slot, total)
