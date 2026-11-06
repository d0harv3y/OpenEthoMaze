"""Shared envelopes for bhvr-cam housing v2.

Units: millimeters.
Datum: outer-shell min corner at origin; +X length, +Y width, +Z up (floor → lid).

BOM (all inside this case):
  Pi Zero W + CSI cam (under board, lens through floor)
  HTU21D breakout (vented −X bay)
  AEDIKO charge/boost (~25×16×4)
  micro-USB charge breakout (HiLetgo-class DIP)
  18650 + spring/slide terminals
  mini slide switch (~8.7×3.7×3.7)
  wiring slack

Assumptions — measure your parts and edit numbers here; rebuild models.
"""

from __future__ import annotations

# --- Outer envelope ------------------------------------------------------
# Side-by-side: 18650 trough (−Y) + Pi column (+Y). Was 76×55; v2 grows for cell.
LENGTH = 112.0
WIDTH = 62.0
BASE_HEIGHT = 30.0
WALL = 2.2
FLOOR = 2.0
CORNER_R = 4.0
LID_LIP = 1.2

# --- Raspberry Pi Zero W -------------------------------------------------
PI_LEN = 65.0
PI_WID = 30.0
PI_HOLE_DX = 58.0
PI_HOLE_DY = 23.0
PI_HOLE_D = 2.7
PI_POST_OD = 6.0
PI_POST_H = 6.0  # clears cam body under board
# Pi column on +Y half; connectors face +Y wall
PI_CX = 68.0  # hole-centroid X (cam / CSI toward +X)
PI_CY = WIDTH - WALL - 4.0 - PI_WID / 2
PI_SHELF_Z = FLOOR

# Data micro-USB + HDMI/power service bay on +Y wall
USB_DATA_W = 12.0
USB_DATA_H = 7.0
USB_DATA_Z = PI_SHELF_Z + PI_POST_H - 1.0
USB_DATA_X_FROM_PI_CX = -6.5
PORT_BAY_W = 42.0
PORT_BAY_H = 9.0

# Lens window in floor under board (cam sits under Zero, opposite lid)
CAM_HOLE_D = 14.0
CAM_HOLE_X = PI_CX + 18.0
CAM_HOLE_Y = PI_CY

# --- 18650 + spring posts ------------------------------------------------
# Nominal cell Ø18 × 65; trough gives diametral clearance + end play for springs.
CELL_BODY_L = 65.0
CELL_D = 18.0
CELL_TROUGH_D = 19.0
CELL_TROUGH_L = 69.0  # body + ~2 mm spring travel each end
CELL_CLIP_POCKET_L = 4.0  # recess behind each spring post
CELL_CLIP_POCKET_W = 12.0
CELL_CLIP_POCKET_H = 12.0
# Trough axis // +X, on −Y side
CELL_CX = PI_CX - 4.0
CELL_CY = WALL + 2.0 + CELL_TROUGH_D / 2
CELL_CZ = FLOOR + CELL_TROUGH_D / 2

# --- AEDIKO charge/boost (B09JZFXD1X class) ------------------------------
CHG_L = 25.0
CHG_W = 16.0
CHG_H = 4.0
# Pocket between cell and Pi near −X of Pi (wiring to BAT / OUT)
CHG_CX = CELL_CX - CELL_TROUGH_L / 2 + CHG_L / 2 + 2.0
CHG_CY = (CELL_CY + PI_CY) / 2
CHG_CZ = FLOOR + CHG_H / 2 + 1.0

# --- Charge micro-USB breakout (HiLetgo DIP class) -----------------------
# PCB ~14–15 mm; jack faces −Y wall for cable access (separate from Pi data USB).
CHG_USB_PCB_L = 15.0
CHG_USB_PCB_W = 14.0
CHG_USB_PCB_H = 5.0
CHG_USB_JACK_W = 8.0
CHG_USB_JACK_H = 3.2
CHG_USB_CX = CHG_CX + 10.0
CHG_USB_CY = WALL + CHG_USB_PCB_W / 2
CHG_USB_CZ = FLOOR + 6.0

# --- Mini slide switch ---------------------------------------------------
# Body ~8.7 W × 3.7 H × 3.7 D; lever needs a wall slot.
SW_W = 8.7
SW_H = 3.7
SW_D = 3.7
SW_SLOT_CLEAR = 0.4
# On −Y wall, near charge jack (power path)
SW_CX = CHG_USB_CX + 18.0
SW_CZ = FLOOR + 8.0

# --- HTU21D vestibule (−X, baffled from Pi heat) -------------------------
HTU_BAY_LEN = 22.0
HTU_VENT_D = 10.0
HTU_VENT_COUNT = 2  # −X wall; keep clear of cell end
HTU_BAFFLE_T = 1.6
HTU_MIN_SEP_FROM_PI = 35.0

# --- Lid mating / mount variants -----------------------------------------
LID_THICK = 2.4
LID_SKIRT = 8.0
LID_SCREW_D = 3.2
LID_TAB_T = 3.0

TRIPOD_THRU_D = 6.6
TRIPOD_NUT_AF = 11.2
TRIPOD_NUT_T = 5.6
TRIPOD_BOSS_OD = 18.0
TRIPOD_BOSS_H = 8.0

KEYHOLE_PITCH = 50.0
KEYHOLE_SLOT_W = 4.2
KEYHOLE_HEAD_D = 9.0
KEYHOLE_HEAD_RECESS = 1.2
