"""Ghost envelopes — BOM fit check (not for print). Open beside base_v2 in the viewer."""

from __future__ import annotations

import sys
from pathlib import Path

from cadgen import build123d as bd
from cadgen import srgb, step

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import dims as d


def _box(lx: float, ly: float, lz: float, at: tuple[float, float, float], label: str, color: str):
    p = bd.Box(lx, ly, lz).moved(bd.Location(at))
    p.label = label
    p.color = srgb(color, 0.45)
    return p


@step(out="../STEP/layout_ghosts.step")
def layout_ghosts():
    parts = [
        _box(d.PI_LEN, d.PI_WID, 1.6, (d.PI_CX, d.PI_CY, d.PI_SHELF_Z + d.PI_POST_H + 0.8), "pi0w", "#4A90D9"),
        _box(12, 12, 8, (d.CAM_HOLE_X, d.CAM_HOLE_Y, d.FLOOR + 5), "csi_cam", "#6B7280"),
        _box(
            d.CELL_BODY_L,
            d.CELL_D,
            d.CELL_D,
            (d.CELL_CX, d.CELL_CY, d.CELL_CZ),
            "18650",
            "#22C55E",
        ),
        _box(d.CHG_L, d.CHG_W, d.CHG_H, (d.CHG_CX, d.CHG_CY, d.CHG_CZ), "aediko_chg", "#F59E0B"),
        _box(
            d.CHG_USB_PCB_L,
            d.CHG_USB_PCB_W,
            d.CHG_USB_PCB_H,
            (d.CHG_USB_CX, d.CHG_USB_CY, d.CHG_USB_CZ),
            "chg_usb_breakout",
            "#A855F7",
        ),
        _box(d.SW_W, d.SW_D, d.SW_H, (d.SW_CX, d.WALL + d.SW_D / 2, d.SW_CZ), "slide_switch", "#EF4444"),
        _box(16, 16, 3, (d.HTU_BAY_LEN / 2 + d.WALL, d.WIDTH / 2, d.FLOOR + 4), "htu21d", "#14B8A6"),
    ]
    asm = bd.Compound(children=parts, label="layout_ghosts")
    return asm


if __name__ == "__main__":
    layout_ghosts()
