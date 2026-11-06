"""Lid with sloping side rails — desk / shelf standing, slight downward tilt."""

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

# Camera end (+X) taller → lens tips slightly down when the lid sits on the desk
WEDGE_HI = 14.0
WEDGE_LO = 4.0
RAIL_W = 8.0


def _rail(y_center: float) -> bd.Part:
    length = d.LENGTH - 2 * d.WALL
    with bd.BuildPart() as part:
        with bd.BuildSketch(bd.Plane.XZ):
            bd.Polygon(
                (-length / 2, 0),
                (length / 2, 0),
                (length / 2, WEDGE_HI),
                (-length / 2, WEDGE_LO),
            )
        bd.extrude(amount=RAIL_W)
    # Sketch on XZ extrudes along +Y from y=0; shift to rail center and lid top
    return part.part.moved(
        bd.Location((d.LENGTH / 2, y_center - RAIL_W / 2, d.LID_THICK))
    )


@step(out="../STEP/lid_desk_stand.step")
@stl(out="../STL/lid_desk_stand.stl")
def lid_desk_stand():
    lid = lid_blank()
    lid += _rail(d.WALL + RAIL_W / 2)
    lid += _rail(d.WIDTH - d.WALL - RAIL_W / 2)
    lid.label = "lid_desk_stand"
    return lid


if __name__ == "__main__":
    lid_desk_stand()
