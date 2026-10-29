# Grill interim live bridge vs jump to MediaMTX

Type: grilling  
Status: resolved  
Blocked by: 01

## Question

Given the MediaMTX research answer, do we **allow an interim** Mode 1 live path (UDP or SSH MPEG-TS + ffmpeg on cam) before MediaMTX, or **jump straight** to the MediaMTX/WebRTC-class stack?

Settle: ship criteria for “good enough” interim; whether cam1 may use interim while the fleet standard waits; explicit reject of annex-B except emergency.

## Answer

**Interim yes** (operator 2026-10-14): push ffmpeg to cam1 and verify **Mode 1 UDP MPEG-TS** before MediaMTX cutover.

- Good enough: focus live moves at usable rate on USB (target toward 720p@30; measure tile fps / bit rate).
- cam1 may use interim while fleet standard waits on MediaMTX.
- Annex-B emergency only (not the Mode 1 path).

Aligns with [Research MediaMTX…](01-research-mediamtx-live-backend.md).

## Verified (2026-10-14, cam1 USB)

- Static armel `~/bin/ffmpeg` on cam1; `live_udp_mpegts.sh` → `udp://192.168.7.1:15550`.
- Raw listen: ~1k+ MPEG-TS packets / 8s (`0x47` sync) from `192.168.7.27`.
- Kiosk `preview.transport: udp` @ 1280×720@30: `GET /api/preview/bhvr-cam1` → HTTP 200, ~315 KiB / 15s.
- Health: `preview_transport=udp`, `roster_size=1`, cam online.
- Do **not** `pkill -f bin/ffmpeg` over SSH (matches the remote shell). Use `killall`.
