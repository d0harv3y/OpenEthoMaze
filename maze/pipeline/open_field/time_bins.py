"""Equal-width time bins for an open-field session (one video).

The row grain of the frailty feature table is one bin, not a maze ``interval``
(``run`` / ``wait``). ``bin_width_s`` is a parameter: 600 s is the first-10 vs
last-10 contrast; 300 s is the same table with finer bins.
"""

from __future__ import annotations

from dataclasses import dataclass

BIN_WIDTH_10MIN_S = 600.0
BIN_WIDTH_5MIN_S = 300.0
DEFAULT_TAIL_SLOP_S = 2.0


@dataclass(frozen=True)
class TimeBin:
    """Half-open window ``[t0_s, t1_s)`` except the last bin, which ends at the video duration."""

    bin_index: int
    t0_s: float
    t1_s: float

    @property
    def duration_s(self) -> float:
        return self.t1_s - self.t0_s


def equal_width_bins(
    duration_s: float,
    bin_width_s: float,
    *,
    tail_slop_s: float = DEFAULT_TAIL_SLOP_S,
) -> list[TimeBin]:
    """Partition ``[0, duration_s]`` into bins of width ``bin_width_s`` starting at 0.

    A remainder shorter than ``tail_slop_s`` is absorbed into the previous bin so a
    1200.05 s file at 600 s still yields two bins. A longer remainder is left out:
    it is not a bin and it is not the "last 10 min."
    """
    if bin_width_s <= 0:
        raise ValueError(f"bin_width_s must be positive, got {bin_width_s}")
    if tail_slop_s < 0:
        raise ValueError(f"tail_slop_s must be non-negative, got {tail_slop_s}")
    if duration_s <= 0:
        return []

    bins: list[TimeBin] = []
    index = 0
    while True:
        t0 = index * bin_width_s
        if t0 >= duration_s:
            break
        t1 = t0 + bin_width_s
        if t1 <= duration_s + 1e-9:
            bins.append(TimeBin(bin_index=index, t0_s=t0, t1_s=min(t1, duration_s)))
            index += 1
            continue
        partial = duration_s - t0
        if bins and partial <= tail_slop_s:
            previous = bins[-1]
            bins[-1] = TimeBin(previous.bin_index, previous.t0_s, duration_s)
        break

    if bins:
        tail = duration_s - bins[-1].t1_s
        if 0 < tail <= tail_slop_s:
            previous = bins[-1]
            bins[-1] = TimeBin(previous.bin_index, previous.t0_s, duration_s)
    return bins


def endpoint_bins(bins: list[TimeBin]) -> tuple[TimeBin, TimeBin] | None:
    """First and last bin when at least two exist.

    At ``bin_width_s=600`` on a ~20 min video this is the first 10 min and the last
    10 min. At ``bin_width_s=300`` the middle bins stay in the table; this pair is
    only the two endpoints.
    """
    if len(bins) < 2:
        return None
    return bins[0], bins[-1]
