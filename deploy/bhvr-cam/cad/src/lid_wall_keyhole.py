"""Lid with dual keyhole slots for wall or ceiling #8-screw mounting."""

from __future__ import annotations

import sys
from pathlib import Path

from cadgen import build123d as bd
from cadgen import step, stl

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import dims as d
from lib.shell import lid_blank


def _keyhole(at_xy: tuple[float, float]) -> bd.Part:
    x, y = at_xy
    z = d.LID_THICK / 2
    head = bd.Cylinder(d.KEYHOLE_HEAD_D / 2, d.LID_THICK + 2).moved(bd.Location((x, y, z)))
    slot = bd.Box(d.KEYHOLE_SLOT_W, 12, d.LID_THICK + 2).moved(
        bd.Location((x, y - 6, z))
    )
    return head + slot


@step(out="../STEP/lid_wall_keyhole.step")
@stl(out="../STL/lid_wall_keyhole.stl")
def lid_wall_keyhole():
    lid = lid_blank()
    cy = d.WIDTH / 2
    for dx in (-d.KEYHOLE_PITCH / 2, d.KEYHOLE_PITCH / 2):
        lid -= _keyhole((d.LENGTH / 2 + dx, cy))
    lid.label = "lid_wall_keyhole"
    return lid


if __name__ == "__main__":
    lid_wall_keyhole()
