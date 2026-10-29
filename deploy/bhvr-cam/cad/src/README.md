# bhvr-cam housing CAD

Parametric remaster of the 2020 SketchUp `pinode` case for **Pi Zero W** + CSI cam + **HTU21D** + **18650** UPS (AEDIKO charge/boost) + charge micro-USB + slide switch.

## CAD vocab (for this project)

| Term | Plain meaning | Where you see it |
|------|---------------|------------------|
| **Envelope** | Bounding box of a part (L×W×H clearance) | numbers in `lib/dims.py` |
| **Datum** | Origin + axes we measure from | min corner of shell; +X/+Y/+Z |
| **Bay / vestibule** | Pocket of air for one subsystem | HTU −X end; charge pocket |
| **Trough** | Open-top cradle (cell drops in) | 18650 bed on −Y side |
| **Boss / post** | Raised cylinder with a screw hole | Pi M2.5 mounts |
| **Cutout / window** | Hole through a wall or floor | data USB, charge jack, cam lens, switch |
| **Baffle** | Interior wall that separates volumes | HTU vs Pi heat |
| **Mate / lid skirt** | How lid seats on the base lip | shared by all `lid_*.py` |
| **Ghost** | Non-print solid showing part size/place | `layout_ghosts.py` |
| **Boolean** | Add (`+`) or subtract (`−`) solids | trough cut from shell |
| **STEP** | Exact CAD solid (viewer + FreeCAD) | `STEP/*.step` |
| **STL** | Triangle mesh for slicing/print | `STL/*.stl` |
| **Parametric** | Change a dim → rebuild geometry | edit `dims.py`, re-run model |

Workflow: **edit dims → run model script → open STEP in viewer**. You rarely “draw” in FreeCAD; the Python *is* the drawing.

## Floor plan (top view)

```
        −Y (charge jack + switch)              +Y (Pi data USB / HDMI)
   ┌────────────────────────────────────────────────────────────┐
−X │ HTU bay │ 18650 trough + springs    │                      │ +X
   │ vents   │ AEDIKO + μUSB breakout    │  Pi Zero W + cam↓    │ cam
   │         │                           │  (lens through floor)│ lens
   └────────────────────────────────────────────────────────────┘
                         lid on +Z
```

## Models

| Script | Output | Role |
|--------|--------|------|
| `base_v2.py` | `STEP/base_v2.step`, `STL/base_v2.stl` | Printable base |
| `layout_ghosts.py` | `STEP/layout_ghosts.step` | BOM envelopes (fit check) |
| `lid_plain.py` | `lid_plain.*` | Blank lid |
| `lid_tripod.py` | `lid_tripod.*` | 1/4-20 nut trap |
| `lid_wall_keyhole.py` | `lid_wall_keyhole.*` | Wall/ceiling keyholes |
| `lid_desk_stand.py` | `lid_desk_stand.*` | Desk wedge rails |

Shared numbers: [`lib/dims.py`](lib/dims.py). Legacy SketchUp/STL: [`../old/`](../old/).

## Build (PowerShell, from `cad/`)

```powershell
$env:PYTHONPATH = "$PWD\src"
$cad = "uvx --no-config --managed-python --python 3.13 --from cadgen==0.7.26"
& ([scriptblock]::Create("$cad python src/base_v2.py"))
& ([scriptblock]::Create("$cad python src/layout_ghosts.py"))
& ([scriptblock]::Create("$cad python src/lid_plain.py"))
# …other lids as needed
& ([scriptblock]::Create("$cad cadgen viewer --host 127.0.0.1 --json --detach"))
```

Or: `uvx … python src/base_v2.py` with `PYTHONPATH` set to `src`.
