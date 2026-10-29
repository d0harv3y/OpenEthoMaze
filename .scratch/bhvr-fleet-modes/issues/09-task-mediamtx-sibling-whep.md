# Task: MediaMTX sibling + `whep` transport (cam1 litmus)

Type: task  
Status: resolved  
Blocked by: 08

## Question

_(Task — implement cutover settled in [08](08-grilling-mediamtx-cutover.md).)_

Ship a **sibling** live path on the NVR without removing interim UDP:

1. **Install** pinned MediaMTX `linux_arm64` on NVR (tarball, not apt); systemd unit; enable WebRTC; `webrtcAdditionalHosts` includes `192.168.7.1` + NVR wlan IP.
2. **Path** per MQTT cam id (`bhvr-cam1`): ingest **UDP MPEG-TS** on port **15550** when `preview.transport: whep` (no auth v1).
3. **Kiosk:** add `preview.transport: whep`; start/stop cam via existing `live_udp_mpegts.sh` publish; focus tile uses **MediaMTXWebRTCReader / WHEP** (not mpegts.js). Leave `udp` / `mpegts` working.
4. **Idle-only:** do not start focus publish while a science session owns the cam (same ownership rules as today).
5. **Litmus on cam1 USB:** measure tile feel vs interim (~10–15 fps / ~1 s). If clearly better, set Mode 1 default to `whep`; document `udp` one-line rollback in config/README.

Done when: cam1 focus over WHEP is litmus-green and default flip (or explicit defer with reason) is recorded on this ticket. Out of scope: Mode 2 RTSP, campus remote WHEP gate, MediaMTX `record:`, science tee.

## Progress 2026-10-14

- MediaMTX **v1.21.2** at `~/bhvr-mediamtx` on NVR; config + unit in `deploy/bhvr-nvr/mediamtx/` + `systemd/bhvr-mediamtx.service`.
- Running **user nohup** for now (`sudo` for systemd needs TTY): `nohup ~/bhvr-mediamtx/mediamtx ~/bhvr-mediamtx/mediamtx.yml`.
- Kiosk synced: `transport: whep`, `POST /api/preview/{id}/whep/start`, vendored `mediamtx-reader.js`.
- API litmus: whep/start → URL; cam rpicam|ffmpeg → `:15550`; MediaMTX WHEP **201** + SDP answer; `preview_idle=["bhvr-cam1"]`.
- **Operator tile feel (2026-10-14):** vs interim UDP→mpegts.js — **about the same / maybe a bit better**; **less latency**; **slightly stabler fps**; still **~15 fps** (not 30). Soft-pass litmus → keep **`whep` default**. FPS ceiling is encode/path follow-on, not a WHEP reject.
- **Rollback:** `preview.transport: udp` in `~/bhvr-kiosk/config.yaml` and stop MediaMTX (`pkill -x mediamtx`) so `:15550` is free.
- **Systemd (on NVR with password):**  
  `sudo cp ~/deploy/bhvr-nvr/systemd/bhvr-mediamtx.service /etc/systemd/system/ && sudo systemctl enable --now bhvr-mediamtx`

## Answer

Sibling MediaMTX + `whep` shipped and accepted as Mode 1 default (soft latency/stability win). Interim `udp` remains one-line fallback. Open follow-on: why focus sticks ~15 fps at requested 720p30 (sensor mode / soft_fps / Zero encode — not MediaMTX routing).
