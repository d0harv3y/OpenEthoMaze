# Grill MediaMTX cutover (sibling WHEP path)

Type: grilling  
Status: resolved  
Blocked by: 01, 07

## Question

Interim Mode 1 UDP MPEG-TS is verified on cam1 (~10–15 fps, ~1 s latency). Research already chose **MediaMTX on NVR + browser WHEP**. This grill settles the **cutover shape** before any install/refactor.

Not in this ticket: Mode 2 WiFi RTSP litmus, MediaMTX `record:` replacing science SSH, Mode 3, tee-while-recording.

## Answer

**Sibling MediaMTX cutover** (operator rubber-stamp 2026-10-14):

| # | Decision |
|---|----------|
| 1 | **Sibling path** — MediaMTX systemd + new transport beside `udp`/`mpegts`; do not delete interim until WHEP litmus wins |
| 2 | **UDP MPEG-TS ingest** — reuse `live_udp_mpegts.sh` into MediaMTX; RTSP later (Mode 2 / follow-up) |
| 3 | **Idle-only focus** while recording — no science-encode tee into MediaMTX in v1 |
| 4 | **NVR kiosk Chromium first** — campus laptop WHEP not a cutover gate; still set `webrtcAdditionalHosts` (gadget + wlan) for later |
| 5 | **Flip Mode 1 default to WHEP** after green litmus; keep `udp` as one-line config fallback |
| 6 | Config token: **`preview.transport: whep`** (`webrtc` stays aiortc legacy) |
| 7 | **Port 15550** mutually exclusive — MediaMTX owns it under `whep`; kiosk remux owns it under `udp` |
| 8 | Browser: **MediaMTXWebRTCReader / WHEP** in focus tile (iframe OK as debug escape) |
| 9 | Path name = **MQTT cam id** (`bhvr-cam1`) |
| 10 | **No publish/read auth** on LAN for v1 |

**Litmus bar:** cam1 USB focus tile clearly smoother / lower latency than interim ~10–15 fps / ~1 s; then flip default.

**Build ticket:** [09-task-mediamtx-sibling-whep.md](09-task-mediamtx-sibling-whep.md).
