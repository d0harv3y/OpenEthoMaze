"""Outer shell / lid profile helpers shared by base and lids."""

from __future__ import annotations

from cadgen import build123d as bd

from lib import dims as d


def outer_box(height: float) -> bd.Part:
    """Rounded rectangular prism; min corner at origin."""
    with bd.BuildPart() as part:
        with bd.BuildSketch() as sk:
            bd.Rectangle(d.LENGTH, d.WIDTH)
            bd.fillet(sk.vertices(), d.CORNER_R)
        bd.extrude(amount=height)
    return part.part.moved(bd.Location((d.LENGTH / 2, d.WIDTH / 2, 0)))


def cavity(height: float, wall: float = d.WALL, floor: float = 0.0) -> bd.Part:
    """Inner cavity solid for subtraction; min corner aligned to outer at origin."""
    inner_l = d.LENGTH - 2 * wall
    inner_w = d.WIDTH - 2 * wall
    inner_r = max(0.5, d.CORNER_R - wall)
    with bd.BuildPart() as part:
        with bd.BuildSketch() as sk:
            bd.Rectangle(inner_l, inner_w)
            bd.fillet(sk.vertices(), inner_r)
        bd.extrude(amount=height)
    return part.part.moved(bd.Location((d.LENGTH / 2, d.WIDTH / 2, floor)))


def lid_blank() -> bd.Part:
    """Plain lid: flat top + skirt that seats on the base lip."""
    top = outer_box(d.LID_THICK)
    outer = outer_box(d.LID_SKIRT).moved(bd.Location((0, 0, -d.LID_SKIRT)))
    inner = cavity(d.LID_SKIRT + 0.2, wall=d.WALL, floor=0).moved(
        bd.Location((0, 0, -d.LID_SKIRT - 0.1))
    )
    skirt = outer - inner
    lid = top + skirt
    for y, sign in ((d.WALL + 1.5, 1), (d.WIDTH - d.WALL - 1.5, -1)):
        tab = bd.Box(10, d.LID_TAB_T, 4).moved(
            bd.Location((d.LENGTH / 2, y + sign * d.LID_TAB_T / 2, -2))
        )
        hole = bd.Cylinder(d.LID_SCREW_D / 2, 8).moved(
            bd.Location((d.LENGTH / 2, y + sign * d.LID_TAB_T / 2, -2))
        )
        lid = lid + tab - hole
    lid.label = "lid"
    return lid
