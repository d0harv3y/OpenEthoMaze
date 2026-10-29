# Research MediaMTX (and peers) for Mode 1 + Mode 2 live

Type: research  
Status: resolved  
Blocked by:

## Question

For bhvr kiosk + NVR + Pi Zero cams, what live-media backend best serves **long-term smoothness** for **Mode 1 (USB, high rate)** and **Mode 2 (WSU-IoT, low rate)**?

Compare at least: current SSH annex-B / SSH MPEG-TS / UDP MPEG-TS vs **MediaMTX** (and brief WebRTC-only alternatives). Recommend a target architecture and whether an interim UDP MPEG-TS bridge is worth it before MediaMTX.

Constraints: cam is armhf Zero W; NVR is aarch64 Pi; no reliable cam apt on WSU-IoT; wired CDC ECM subnet `192.168.7.0/24`; kiosk is local FastAPI + browser.

## Comments

### Answer draft (2026-10-14)

**Target:** MediaMTX on the NVR (linux_arm64); cams publish HW H.264 (RTSP preferred; UDP MPEG-TS OK on Mode 1 gadget); browser focus via WebRTC WHEP. Do not run cam-local `rpiCamera` as fleet standard. Do not deepen aiortc.

**Interim:** Yes — Mode 1 UDP MPEG-TS → mpegts.js is worth verifying before MediaMTX cutover; Mode 2 keeps SSH MPEG-TS until RTSP/WHEP litmus. Annex-B emergency only.

Full write-up: [research/mediamtx-live-backend.md](../research/mediamtx-live-backend.md)

## Answer

**Target:** MediaMTX on the NVR (linux_arm64). Cams publish one HW H.264 stream (RTSP preferred; UDP MPEG-TS OK on Mode 1 USB). Kiosk browser reads WebRTC WHEP. Do not standardize cam-local `rpiCamera`; do not deepen aiortc.

**Interim:** Yes — verify Mode 1 UDP MPEG-TS → mpegts.js before MediaMTX cutover; Mode 2 keeps SSH MPEG-TS until RTSP/WHEP litmus. Annex-B emergency only.

**Evidence:** [research/mediamtx-live-backend.md](../research/mediamtx-live-backend.md) (via [MediaMTX live backend research](11a4d005-d123-40fd-90b8-cd15c01e4d97)).

**Surfaced for later:** while recording, does focus tee the science encode into MediaMTX, or stay idle-only second encode? → map fog / follow-on grill.
