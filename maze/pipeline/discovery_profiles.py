from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscoveryProfile:
    """Dataset-specific discovery quirks kept separate from algorithm defaults."""

    max_trial_num: int = 9
    max_session_num: int = 5
    session_renumber: dict[str, int] = field(default_factory=dict)


DEFAULT_DISCOVERY_PROFILE = DiscoveryProfile(
    session_renumber={
        "556": -1,
        "557": -1,
        "558": -1,
        "559": -1,
    }
)
