"""bhvr-cam base v2 — Pi + cam, 18650 trough, charge bay, switch, HTU vestibule."""

from __future__ import annotations

import sys
from pathlib import Path

from cadgen import build123d as bd
from cadgen import step, stl

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import dims as d
from lib.shell import cavity, outer_box


def _pi_posts() -> bd.Part:
    posts = None
    for dx in (-d.PI_HOLE_DX / 2, d.PI_HOLE_DX / 2):
        for dy in (-d.PI_HOLE_DY / 2, d.PI_HOLE_DY / 2):
            x = d.PI_CX + dx
            y = d.PI_CY + dy
            post = bd.Cylinder(d.PI_POST_OD / 2, d.PI_POST_H).moved(
                bd.Location((x, y, d.PI_SHELF_Z + d.PI_POST_H / 2))
            )
            bore = bd.Cylinder(d.PI_HOLE_D / 2, d.PI_POST_H + 2).moved(
                bd.Location((x, y, d.PI_SHELF_Z + d.PI_POST_H / 2))
            )
            piece = post - bore
            posts = piece if posts is None else posts + piece
    return posts


def _cylinder_x(radius: float, length: float, at: tuple[float, float, float]) -> bd.Part:
    return bd.Cylinder(radius, length).rotate(bd.Axis.Y, 90).moved(bd.Location(at))


def _cylinder_y(radius: float, length: float, at: tuple[float, float, float]) -> bd.Part:
    return bd.Cylinder(radius, length).rotate(bd.Axis.X, 90).moved(bd.Location(at))


def _cell_trough() -> bd.Part:
    """Cylindrical bed + end pockets for spring/slide terminals."""
    bed = _cylinder_x(d.CELL_TROUGH_D / 2, d.CELL_TROUGH_L, (d.CELL_CX, d.CELL_CY, d.CELL_CZ))
    # Open the trough upward so the cell drops in from above
    open_top = bd.Box(d.CELL_TROUGH_L + 1, d.CELL_TROUGH_D + 1, d.CELL_TROUGH_D).moved(
        bd.Location((d.CELL_CX, d.CELL_CY, d.CELL_CZ + d.CELL_TROUGH_D / 2))
    )
    trough = bed + open_top
    for sign in (-1.0, 1.0):
        x = d.CELL_CX + sign * (d.CELL_TROUGH_L / 2 + d.CELL_CLIP_POCKET_L / 2 - 0.5)
        pocket = bd.Box(d.CELL_CLIP_POCKET_L, d.CELL_CLIP_POCKET_W, d.CELL_CLIP_POCKET_H).moved(
            bd.Location((x, d.CELL_CY, d.FLOOR + d.CELL_CLIP_POCKET_H / 2))
        )
        trough = trough + pocket
    return trough


@step(out="../STEP/base_v2.step")
@stl(out="../STL/base_v2.stl")
def base_v2():
    shell = outer_box(d.BASE_HEIGHT)
    hollow = cavity(d.BASE_HEIGHT - d.FLOOR + 0.2, floor=d.FLOOR)
    body = shell - hollow

    # --- HTU vestibule (−X) ----------------------------------------------
    baffle_x = d.HTU_BAY_LEN + d.WALL
    baffle = bd.Box(d.HTU_BAFFLE_T, d.WIDTH - 2 * d.WALL, d.BASE_HEIGHT - d.FLOOR - 2).moved(
        bd.Location(
            (
                baffle_x + d.HTU_BAFFLE_T / 2,
                d.WIDTH / 2,
                d.FLOOR + (d.BASE_HEIGHT - d.FLOOR - 2) / 2,
            )
        )
    )
    i2c_pass = bd.Box(d.HTU_BAFFLE_T + 1, 8, 4).moved(
        bd.Location((baffle_x + d.HTU_BAFFLE_T / 2, d.WIDTH / 2, d.FLOOR + 3))
    )
    body = body + baffle - i2c_pass

    vent_y0 = d.WIDTH / 2 - (d.HTU_VENT_COUNT - 1) * 10
    for i in range(d.HTU_VENT_COUNT):
        y = vent_y0 + i * 20
        body -= _cylinder_x(d.HTU_VENT_D / 2, d.WALL + 4, (d.WALL / 2, y, d.FLOOR + 10))
    body -= bd.Cylinder(d.HTU_VENT_D / 2, d.FLOOR + 2).moved(
        bd.Location((d.HTU_BAY_LEN / 2 + d.WALL, d.WIDTH / 2, d.FLOOR / 2))
    )

    # --- 18650 trough + clip pockets -------------------------------------
    body -= _cell_trough()

    # --- Charge IC pocket (clearance box) --------------------------------
    body -= bd.Box(d.CHG_L + 1, d.CHG_W + 1, d.CHG_H + 2).moved(
        bd.Location((d.CHG_CX, d.CHG_CY, d.CHG_CZ))
    )

    # --- Charge micro-USB breakout + jack through −Y wall ----------------
    body -= bd.Box(d.CHG_USB_PCB_L + 1, d.CHG_USB_PCB_W + 1, d.CHG_USB_PCB_H + 2).moved(
        bd.Location((d.CHG_USB_CX, d.CHG_USB_CY, d.CHG_USB_CZ))
    )
    body -= bd.Box(d.CHG_USB_JACK_W, d.WALL + 3, d.CHG_USB_JACK_H).moved(
        bd.Location((d.CHG_USB_CX, d.WALL / 2, d.CHG_USB_CZ))
    )

    # --- Slide switch slot in −Y wall ------------------------------------
    body -= bd.Box(d.SW_W + d.SW_SLOT_CLEAR, d.WALL + 3, d.SW_H + d.SW_SLOT_CLEAR).moved(
        bd.Location((d.SW_CX, d.WALL / 2, d.SW_CZ))
    )
    # Inner recess for switch body
    body -= bd.Box(d.SW_W + 1, d.SW_D + 1, d.SW_H + 1).moved(
        bd.Location((d.SW_CX, d.WALL + d.SW_D / 2, d.SW_CZ))
    )

    # --- Pi service bay (+Y) + data USB window ---------------------------
    body -= bd.Box(d.PORT_BAY_W, d.WALL + 2, d.PORT_BAY_H).moved(
        bd.Location((d.PI_CX, d.WIDTH - d.WALL / 2, d.USB_DATA_Z + d.PORT_BAY_H / 2))
    )
    usb_x = d.PI_CX + d.USB_DATA_X_FROM_PI_CX
    body -= bd.Box(d.USB_DATA_W, d.WALL + 2, d.USB_DATA_H).moved(
        bd.Location((usb_x, d.WIDTH - d.WALL / 2, d.USB_DATA_Z + d.USB_DATA_H / 2))
    )

    # --- Cam lens through floor (under board, opposite lid) --------------
    body -= bd.Cylinder(d.CAM_HOLE_D / 2, d.FLOOR + 2).moved(
        bd.Location((d.CAM_HOLE_X, d.CAM_HOLE_Y, d.FLOOR / 2))
    )

    # Lid screw holes
    for y in (d.WALL / 2, d.WIDTH - d.WALL / 2):
        body -= _cylinder_y(
            d.LID_SCREW_D / 2, d.WALL + 4, (d.LENGTH / 2, y, d.BASE_HEIGHT - 5)
        )

    body += _pi_posts()
    body.label = "base_v2"
    return body


if __name__ == "__main__":
    base_v2()
