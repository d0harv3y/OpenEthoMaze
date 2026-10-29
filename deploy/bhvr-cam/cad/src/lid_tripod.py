"""Lid with centered 1/4-20 nut trap for tripod / ball-head / clamp mounts."""

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


def _hex_prism(across_flats: float, height: float) -> bd.Part:
    r = across_flats / (3**0.5)  # apothem → vertex radius for regular hex
    with bd.BuildPart() as part:
        with bd.BuildSketch():
            bd.RegularPolygon(r, 6)
        bd.extrude(amount=height)
    return part.part


@step(out="../STEP/lid_tripod.step")
@stl(out="../STL/lid_tripod.stl")
def lid_tripod():
    lid = lid_blank()
    cx, cy = d.LENGTH / 2, d.WIDTH / 2
    boss = bd.Cylinder(d.TRIPOD_BOSS_OD / 2, d.TRIPOD_BOSS_H).moved(
        bd.Location((cx, cy, d.LID_THICK + d.TRIPOD_BOSS_H / 2))
    )
    thru = bd.Cylinder(d.TRIPOD_THRU_D / 2, d.LID_THICK + d.TRIPOD_BOSS_H + 2).moved(
        bd.Location((cx, cy, (d.LID_THICK + d.TRIPOD_BOSS_H) / 2))
    )
    nut = _hex_prism(d.TRIPOD_NUT_AF, d.TRIPOD_NUT_T).moved(
        bd.Location((cx, cy, d.LID_THICK + d.TRIPOD_NUT_T / 2 + 0.4))
    )
    lid = lid + boss - thru - nut
    lid.label = "lid_tripod"
    return lid


if __name__ == "__main__":
    lid_tripod()
