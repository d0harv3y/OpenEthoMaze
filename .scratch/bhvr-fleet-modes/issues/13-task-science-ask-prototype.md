# Task: science-ask prototype (4:3 Standard/Lite + display decimation)

Type: task  
Status: in progress  
Blocked by: 11  
Claimed: 2026-10-19

## Question

Ship v0 per grill [11](11-grilling-encode-presets-menu.md) Q15–Q16:

1. Kill operator sensor-mode context menu / PUT surface.
2. Science ask = **Standard** (`1296×972` / `--mode 1296:972`) or **Lite** (`640×480` / `--mode 640:480`) × soft fps `{30,20*,15,10}` in session Start modal.
3. Idle (no session): always **Lite@10**, `buffer_count=6`.
4. Mid-record: science ask **read-only** badge.
5. All online tiles show live (no focus); shrink-to-fit; **display** keep 1/N (default N=10) + slider; honesty badge.
6. Tests for encode-ask map + idle geom.

Done when: local pytest green; operator can start a session with Standard@20 without seeing sensor modes; tiles auto-live with honesty strip.

## Comments

### Progress 2026-10-19

Shipped in tree (`deploy/bhvr-kiosk/`):

- `app/encode_ask.py` — Standard/Lite × fps map; idle Lite@10; buf=6
- Science start uses baked `--mode` + geom + `--buffer-count`; sensor-mode PUT → **410**
- Start modal: touch chips; mid-record science badge read-only
- Context menu: no sensor modes; live on/off + record/meta
- Tiles: auto-live online cams; `live-on`; honesty badge + display 1/N slider
- `config.example.yaml` updated; tests **12 passed**

**Still on operator:** sync tree to NVR; merge live `config.yaml` `profiles:` → `standard`/`lite` (legacy aliases still normalize). True NVR Stage‑B decode-less skip = follow-on.

### Deploy smoke 2026-10-20 (bhvr-nvr0)

Script: `deploy/bhvr-nvr/scripts/_deploy_science_ask.sh`

- Config patched: `profiles=[standard,lite]`, `default_profile=standard`
- Import litmus OK; uvicorn restarted (no sudo)
- Health OK; roster 4; sensor-mode PUT → **410**
- Index: Science size chips + honesty + decimate; no Sensor mode menu
- `whep/start` cam0 → `sensor_mode: 640:480` (idle Lite@10)
- Follow-up: `preview_idle` = all 4 cams; cam1 cmdline: `--mode 640:480:10:P --width 640 --height 480 --framerate 10 --buffer-count 6`
