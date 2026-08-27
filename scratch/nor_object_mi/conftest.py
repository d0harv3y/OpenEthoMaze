"""Put ``scratch/`` on sys.path so ``import nor_object_mi`` works under pytest."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))
