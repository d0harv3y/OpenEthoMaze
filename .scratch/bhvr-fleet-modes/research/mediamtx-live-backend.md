# Research: MediaMTX (and peers) for Mode 1 + Mode 2 live

**Ticket:** [.scratch/bhvr-fleet-modes/issues/01-research-mediamtx-live-backend.md](../issues/01-research-mediamtx-live-backend.md)  
**Date:** 2026-10-14  
**Domain:** bhvr kiosk + NVR + Pi Zero W cams (`deploy/bhvr-kiosk`, `deploy/bhvr-cam`)

## Question

For long-term **focus-live** smoothness under **Mode 1** (USB CDC ECM, high rate ~720p30) and **Mode 2** (WSU-IoT WiFi, low rate), what live-media backend should the fleet standardize on? Compare current kiosk transports vs **MediaMTX** and brief WebRTC-only peers. Recommend a target architecture and whether an interim **UDP MPEG-TS** bridge is worth shipping before MediaMTX.

## Acronyms

| Term | Meaning |
|------|---------|
| NVR | Network Video Recorder host (Pi aarch64 running kiosk + Mosquitto + session SSD) |
| CDC ECM | USB Communications Device Class / Ethernet Control Model (gadget subnet `192.168.7.0/24`) |
| MPEG-TS | MPEG Transport Stream (188-byte packets; browser via mpegts.js / MSE) |
| MSE | Media Source Extensions (browser transmux path used by mpegts.js) |
| WebRTC | Web Real-Time Communication (browser native RTP/ICE) |
| WHEP / WHIP | WebRTC-HTTP Egress / Ingest Protocols (MediaMTX browser read / publish) |
| RTSP | Real Time Streaming Protocol |
| HLS / LL-HLS | HTTP Live Streaming / low-latency HLS |
| aiortc | Python WebRTC stack used by current `webrtc_preview.py` |

Mode definitions: [deploy/GLOSSARY.md](../../../deploy/GLOSSARY.md) (Mode 1 wired live, Mode 2 wireless live).

---

## Verdict (short)

**Target:** run **MediaMTX on the NVR** (linux_arm64 binary); cams keep **one** `rpicam-vid` HW H.264 encode and **publish** into MediaMTX (prefer **RTSP**, Mode 1 can use **UDP MPEG-TS**); kiosk browser reads **WebRTC WHEP** (or iframe `:8889/path`) for focus tiles. Keep science archive as today’s NVR SSH annex-B pipe (or later a MediaMTX record/tee decision — out of scope to freeze here).

**Interim:** **yes** — ship/verify **UDP MPEG-TS → NVR → mpegts.js** on Mode 1 (gadget) as a bridge; keep **SSH MPEG-TS** as Mode 2 default until MediaMTX WHEP is litmus-green. Do **not** deepen **aiortc** or **ssh_annex_b** as the long-term path.

---

## Current paths in `deploy/bhvr-kiosk`

Config knobs: `preview.transport` ∈ `mpegts` | `udp` | `webrtc` | `ssh_annex_b` ([config.example.yaml](../../../deploy/bhvr-kiosk/config.example.yaml), [preview.py](../../../deploy/bhvr-kiosk/app/preview.py)). Example Mode 1-ish defaults already point at gadget ingress (`nvr_host: 192.168.7.1`, 1280×720@30, 2500 kbps).

| Transport | Cam → NVR | NVR → browser | Strengths | Weaknesses for fleet |
|-----------|-----------|---------------|-----------|----------------------|
| **`ssh_annex_b`** | SSH stdout raw H.264 annex-B | jmuxer / MSE feed | Minimal mux on cam | Documented choppy on Zero W WiFi; fragile NAL boundaries under tee ([preview.py](../../../deploy/bhvr-kiosk/app/preview.py) module docstring; [main.py](../../../deploy/bhvr-kiosk/app/main.py) capture tee comments) |
| **`mpegts` (SSH)** | SSH: `rpicam-vid \| ffmpeg -f mpegts pipe:1` | HTTP `video/mp2t` → **mpegts.js** | TCP reliability on campus WiFi; current “known-good” restore path ([`_restore_mpegts_preview.sh`](../../../deploy/bhvr-kiosk/scripts/_restore_mpegts_preview.sh)) | Extra SSH + ffmpeg per focus; doubles process load on Zero; not a real media router |
| **`udp`** | Cam `live_udp_mpegts.sh` → `udp://NVR:port` | NVR ffmpeg remux → HTTP MPEG-TS → mpegts.js | Lower SSH overhead; natural fit for USB gadget LAN; same browser player as SSH MPEG-TS | Lossy; WiFi jitter → black frames if latency chase is aggressive ([index.html](../../../deploy/bhvr-kiosk/app/templates/index.html) disables `liveBufferLatencyChasing`); needs cam `ffmpeg` already present |
| **`webrtc` (aiortc)** | Same UDP MPEG-TS publish | aiortc `MediaPlayer` on UDP → SDP answer | Native WebRTC in browser | Sync MediaPlayer blocks event loop; recording focus falls back / rejects WebRTC ([main.py](../../../deploy/bhvr-kiosk/app/main.py) `/api/preview/.../webrtc`); Python + FFmpeg decode path on NVR; not multi-path production media server |

Science record today is **separate**: SSH `rpicam-vid … --save-pts … -o -` written to NVR `*_video.h264` ([main.py](../../../deploy/bhvr-kiosk/app/main.py) capture start). Focus live must not `pkill` that encode while a session owns the cam (idle vs tee split already encoded in the API).

**mpegts.js role:** HTML5 live MPEG-TS → fragmented MP4 via MSE; optimized for low-latency live; HTTP/WebSocket transport ([xqq/mpegts.js README](https://github.com/xqq/mpegts.js)). Good interim browser sink; not a substitute for congestion-controlled WebRTC on flaky WiFi.

**aiortc role:** Python WebRTC + `MediaPlayer` (FFmpeg-backed file/URL source) ([aiortc helpers docs](https://aiortc.readthedocs.io/en/latest/helpers.html)). Fine for prototypes; wrong long-term home for multi-cam Mode 1/2 routing, ICE, and protocol conversion.

---

## MediaMTX (primary)

Upstream: [bluenviron/mediamtx](https://github.com/bluenviron/mediamtx), docs [mediamtx.org](https://mediamtx.org/). Current release checked: **v1.21.2** (2026-10-08) with standalone binaries including **`linux_arm64`**, **`linux_armv7`**, **`linux_armv6`** ([GitHub releases API](https://api.github.com/repos/bluenviron/mediamtx/releases/latest)) — matches NVR aarch64 and Zero W armhf without cam apt.

Relevant capabilities:

1. **Publish** via RTSP (recommended for FFmpeg), RTMP, SRT, WHIP, **MPEG-TS over UDP**, RTP, plus native **`source: rpiCamera`** when the server runs on the Pi with the camera ([Publish with FFmpeg](https://mediamtx.org/docs/publish/ffmpeg), [Raspberry Pi Cameras](https://mediamtx.org/docs/publish/raspberry-pi-cameras)).
2. **Read** in browsers via **WebRTC** (`http://host:8889/path`, embed via iframe or `MediaMTXWebRTCReader` + **WHEP**), HLS (`:8888`), Media-over-QUIC ([Read with Web browsers](https://mediamtx.org/docs/read/web-browsers)).
3. Automatic **protocol conversion** between publish and read ([README feature list](https://raw.githubusercontent.com/bluenviron/mediamtx/main/README.md)).
4. Optional **record** to fMP4 / MPEG-TS ([Record streams](https://mediamtx.org/docs/features/record)) — possible future science path, but bhvr pts-on-cam + NVR annex-B archive should stay authoritative until a dedicated migration ticket.
5. **Zero dependency** single binary; OpenWrt/docs explicitly list armv6/armv7/arm64 ([Install](https://mediamtx.org/docs/kickoff/install)) — aligns with “unreliable cam apt on WSU-IoT” + USB offline deb/binary push.

### Two deployment shapes (only one recommended)

| Shape | Where MediaMTX runs | How cam feeds | Fit for bhvr |
|-------|---------------------|---------------|--------------|
| **A. NVR router (recommended)** | NVR `linux_arm64` | Cam `rpicam-vid \| ffmpeg` → RTSP publish or `udp+mpegts` path | One router for all cams; kiosk FastAPI stays control plane; browser WHEP to NVR; USB `192.168.7.1` and wlan IP both work as publish targets |
| **B. Cam-local `rpiCamera`** | Each Zero `linux_armv6` | MediaMTX owns libcamera | Attractive for single-Pi demos; **poor fleet fit**: competes with science encode ownership, Zero CPU/RAM, Docker armv6 sunset called out upstream ([issue #5590](https://github.com/bluenviron/mediamtx/issues/5590) — prefer standalone binary on Zero; still heavy for multi-mode kiosk orchestration) |

NETWORK.md already anticipates “tap tile = full-quality focus … # MediaMTX later” ([deploy/NETWORK.md](../../../deploy/NETWORK.md) § Kiosk UI).

---

## Mode 1 vs Mode 2 mapping

| Mode | Backhaul | Rate intent | Publish into MediaMTX | Browser read |
|------|----------|-------------|------------------------|--------------|
| **1 Wired** | CDC ECM `192.168.7.x` → NVR `.1` | High (~720p30 soft) | Prefer **UDP MPEG-TS** or RTSP/TCP on gadget LAN (loss rare; low overhead) | WebRTC WHEP on NVR (smooth tile) |
| **2 Wireless** | WSU-IoT | Low rate | Prefer **RTSP over TCP** (or keep SSH MPEG-TS until RTSP litmus) — UDP alone repeats today’s WiFi black-frame pathology | WebRTC WHEP; if ICE/NAT weird on campus, HLS fallback (higher latency, fewer connectivity issues per MediaMTX docs) |

Kiosk stays **local FastAPI + browser**: replace `/api/preview/{id}` byte pumps with either (a) proxy/redirect to MediaMTX WHEP URL per cam path, or (b) embed `reader.js` against `http://nvr:8889/{cam_id}/whep` while FastAPI only starts/stops cam publishers and enforces session ownership.

---

## Brief WebRTC-only alternatives

| Option | Role | Why not target |
|--------|------|----------------|
| **Deepen aiortc** | Already in-tree | Per-cam Python PeerConnections + FFmpeg MediaPlayer; no RTSP/HLS/record ecosystem; recording path already incomplete |
| **go2rtc** | Popular RTSP↔WebRTC gateway (often with Home Assistant / Frigate) | Viable peer; weaker first-party Pi camera source vs MediaMTX `rpiCamera`; bhvr map already biased MediaMTX; secondary candidate if NVR MediaMTX WHEP fails litmus |
| **Janus / mediasoup / Pion apps** | Full SFU stacks | Overkill for 1-focus / few cams; more ops surface than a single MediaMTX binary |

---

## Interim UDP MPEG-TS before MediaMTX?

**Yes, worth it — scoped.**

| Allow interim when… | Reject interim when… |
|---------------------|----------------------|
| Mode 1 gadget litmus: UDP packets reach `192.168.7.1:udp_port`, mpegts.js plays without black, soft fps ≈ request | Treating UDP as Mode 2 fleet standard |
| Cam already has `ffmpeg` (USB-pushed / offline debs — see fleet map tickets 04/06) | Spending weeks polishing aiortc |
| Science SSH archive unchanged; focus uses separate idle encode or tee rules already in kiosk | Reintroducing annex-B as default |

**Rationale:** Mode 1 backhaul is a quiet L2 LAN; the existing `live_udp_mpegts.sh` + `transport: udp` path reuses mpegts.js and proves cam→NVR publish semantics that MediaMTX will ingest almost unchanged (`source: udp+mpegts://…` per [FFmpeg publish docs](https://mediamtx.org/docs/publish/ffmpeg)). That de-risks MediaMTX path config without freezing the browser on MSE forever.

**SSH MPEG-TS** remains the **Mode 2 interim** (TCP). Jumping straight to MediaMTX on Mode 2 without a wired UDP litmus is higher risk (ICE + campus WiFi + Zero publish in one cut).

**Annex-B:** emergency only (matches grilling ticket 07 framing).

---

## Recommended target architecture

```text
 Pi Zero W (armhf)                    Pi NVR (aarch64)
 ┌─────────────────────┐              ┌──────────────────────────────┐
 │ rpicam-vid H.264 HW │              │ MediaMTX (linux_arm64)       │
 │   ├─ science: SSH   │── annex-B ──▶│   paths: /bhvr-camN          │
 │   │   stdout → NVR  │   (record)   │   publish: RTSP and/or       │
 │   └─ focus: ffmpeg  │── RTSP/UDP ─▶│         udp+mpegts           │
 │      publish        │              │   read: WebRTC :8889 (WHEP)  │
 └─────────────────────┘              │ FastAPI kiosk :8080          │
                                      │   roster / session / start   │
                                      │   publisher / ownership      │
                                      │ Browser ← WHEP / iframe      │
                                      └──────────────────────────────┘
 Mode 1: publish to 192.168.7.1
 Mode 2: publish to NVR wlan IP (RTSP/TCP preferred)
```

**Implementation notes (for later tickets, not this research):**

1. Install MediaMTX on NVR via pinned release tarball (no apt required); systemd unit; `webrtcAdditionalHosts` includes gadget + wlan IPs ([Install docker note](https://mediamtx.org/docs/kickoff/install) applies equally to ICE host candidates).
2. Per-cam path names = MQTT cam ids; publisher auth optional on LAN.
3. Replace aiortc path; keep mpegts.js only as fallback during cutover.
4. Do **not** require MediaMTX on cams for v1; push armv6 binary only if a Mode 3 / edge experiment needs it.
5. Science record vs MediaMTX `record:` stays a separate decision (pts fidelity, NWB pipeline).

---

## Confidence & open questions

| Claim | Confidence | Notes |
|-------|------------|-------|
| MediaMTX-on-NVR + WHEP is best long-term smoothness | **High** | Matches official publish/read matrix and fleet constraints |
| Cam-local `rpiCamera` as fleet standard | **Low** | Wrong ownership vs science SSH encode |
| Interim Mode 1 UDP MPEG-TS worth it | **High** | Reuses in-repo scripts; same publish shape as MediaMTX UDP source |
| Mode 2 RTSP/TCP publish will beat SSH MPEG-TS | **Medium** | Needs litmus on WSU-IoT; SSH MPEG-TS stays safety net |
| MediaMTX record replaces SSH science pipe soon | **Low / unset** | pts + NeuroConv assumptions not verified here |

**Clarify before build:**

1. While recording, is focus-live allowed to share the science encode (tee into MediaMTX) or must it stay a second encode only when idle?
2. Is browser WebRTC from the kiosk Chromium on the NVR touchscreen (same host as MediaMTX) enough, or must remote laptops on campus WiFi also play WHEP?

---

## Sources

### Upstream / official

- MediaMTX README: https://raw.githubusercontent.com/bluenviron/mediamtx/main/README.md  
- Install: https://mediamtx.org/docs/kickoff/install  
- Publish FFmpeg (RTSP + UDP MPEG-TS): https://mediamtx.org/docs/publish/ffmpeg  
- Publish Raspberry Pi Cameras (`rpiCamera`): https://mediamtx.org/docs/publish/raspberry-pi-cameras  
- Read Web browsers (WebRTC / WHEP / HLS): https://mediamtx.org/docs/read/web-browsers  
- Record: https://mediamtx.org/docs/features/record  
- Releases (v1.21.2 arm64/armv7/armv6 assets): https://github.com/bluenviron/mediamtx/releases  
- Pi Zero Docker armv6 caution: https://github.com/bluenviron/mediamtx/issues/5590  
- mpegts.js: https://github.com/xqq/mpegts.js  
- aiortc MediaPlayer: https://aiortc.readthedocs.io/en/latest/helpers.html  

### This repo

- [deploy/bhvr-kiosk/app/preview.py](../../../deploy/bhvr-kiosk/app/preview.py)  
- [deploy/bhvr-kiosk/app/webrtc_preview.py](../../../deploy/bhvr-kiosk/app/webrtc_preview.py)  
- [deploy/bhvr-kiosk/app/main.py](../../../deploy/bhvr-kiosk/app/main.py) (preview + capture)  
- [deploy/bhvr-kiosk/app/templates/index.html](../../../deploy/bhvr-kiosk/app/templates/index.html)  
- [deploy/bhvr-cam/scripts/live_udp_mpegts.sh](../../../deploy/bhvr-cam/scripts/live_udp_mpegts.sh)  
- [deploy/bhvr-kiosk/config.example.yaml](../../../deploy/bhvr-kiosk/config.example.yaml)  
- [deploy/GLOSSARY.md](../../../deploy/GLOSSARY.md), [deploy/NETWORK.md](../../../deploy/NETWORK.md)  
- Wayfinder map: [../map.md](../map.md)  
