"""Plain lid — mates to base_v2, no mount features."""

from __future__ import annotations

import sys
from pathlib import Path

from cadgen import step, stl

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.shell import lid_blank


@step(out="../STEP/lid_plain.step")
@stl(out="../STL/lid_plain.stl")
def lid_plain():
    lid = lid_blank()
    lid.label = "lid_plain"
    return lid


if __name__ == "__main__":
    lid_plain()
