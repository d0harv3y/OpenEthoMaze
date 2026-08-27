"""Quick litmus for absorb_short_bouts (no frames discarded)."""

from __future__ import annotations

import numpy as np

from nor_object_mi.syllable_cleanup import absorb_short_bouts


def test_absorb_bridge_and_length_preserved() -> None:
    # Flanking runs are long enough so only the single-frame bridge is short.
    z = np.array([1, 1, 1, 2, 1, 1, 1, 3, 3, 3], dtype=np.int64)
    out = absorb_short_bouts(z, min_len=3)
    assert out.size == z.size
    assert out.tolist() == [1, 1, 1, 1, 1, 1, 1, 3, 3, 3]


def test_absorb_to_longer_neighbor() -> None:
    z = np.array([1, 1, 1, 1, 2, 3, 3], dtype=np.int64)
    out = absorb_short_bouts(z, min_len=3)
    # 2 absorbed to left (longer) → four 1s then three 3s after 2-frame 3s also? 
    # after absorbing 2 into left: [1,1,1,1,1,3,3] — still short 3s length 2
    # then absorb 3s into left: all 1s
    assert out.tolist() == [1, 1, 1, 1, 1, 1, 1]
