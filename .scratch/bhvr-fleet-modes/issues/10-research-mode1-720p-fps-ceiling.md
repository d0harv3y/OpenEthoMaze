# Research: Mode 1 720p presented ~15 fps vs soft 30

Type: research  
Status: resolved  
Blocked by: 09

## Question

On cam1 (Pi Zero W + OV5647, USB Mode 1, MediaMTX WHEP), focus tile shows **~15 fps** while kiosk requests **1280×720 @ soft 30**. Is the ceiling in MediaMTX/browser, USB, or cam encode? What honest Mode 1 fps budget should we set?

## Answer

**Cam encode ceiling, not MediaMTX/USB.** `--save-pts` at 720p soft 30 → **achieved ≈ 15.5 fps** (`med_dt` 66.7 ms). Browser matches. Fixed shutter did not unlock 30. 480p achieves ~23. `avahi-daemon` often 25–70% CPU on the single core — stop+remeasure needs sudo (not done).

**Budget:** Mode 1 focus **720p @ soft 15** (honest) or **480p @ soft 30** for higher presented fps. Do not advertise soft 30 @ 720p on Zero+OV5647.

**Evidence:** [research/mode1-720p-fps-ceiling.md](../research/mode1-720p-fps-ceiling.md).
