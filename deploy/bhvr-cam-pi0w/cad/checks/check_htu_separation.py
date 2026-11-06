"""Litmus: HTU floor vent center must stay ≥ HTU_MIN_SEP_FROM_PI from Pi centroid."""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from lib import dims as d


def main() -> int:
    htu = (d.HTU_BAY_LEN / 2 + d.WALL, d.WIDTH / 2)
    pi = (d.PI_CX, d.PI_CY)
    sep = math.hypot(htu[0] - pi[0], htu[1] - pi[1])
    print(f"HTU floor vent → Pi centroid: {sep:.1f} mm (min {d.HTU_MIN_SEP_FROM_PI})")
    if sep < d.HTU_MIN_SEP_FROM_PI:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
