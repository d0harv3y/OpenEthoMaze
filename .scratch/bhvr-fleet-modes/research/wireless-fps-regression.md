# Research: Mode 2 wireless focus-live FPS regression (~15 → ~5 → soft ~10)

**Ticket:** [.scratch/bhvr-fleet-modes/issues/02-research-wireless-fps-regression.md](../issues/02-research-wireless-fps-regression.md)  
**Date:** 2026-10-14  
**Scope:** Explain the observed wireless focus-live rate arc on WSU-IoT; name levers; recommend a **Mode 2 fps budget** and transport path. **No live config changes** in this ticket.

## Acronyms

| Term | Meaning |
|------|---------|
| NVR | Network Video Recorder host (Pi running kiosk + Mosquitto + session storage) |
| WSU-IoT | Campus IoT Wi‑Fi SSID used as Mode 2 backhaul |
| FPS | Frames per second (request vs presented vs pts-achieved — disambiguated below) |
| Soft fps | Encoder `--framerate` *request* to `rpicam-vid`; not a scientific claim |
| Focus live | Kiosk single-tile preview stream ([deploy/GLOSSARY.md](../../../deploy/GLOSSARY.md)) |
| MPEG-TS | MPEG Transport Stream (browser via mpegts.js / MSE) |
| MSE | Media Source Extensions |
| SSH MPEG-TS | Cam `rpicam-vid \| ffmpeg -f mpegts` over SSH TCP → HTTP `video/mp2t` |
| UDP MPEG-TS | Cam publishes MPEG-TS to NVR UDP port; NVR remuxes to HTTP for the browser |
| Annex-B | Raw H.264 NAL stream (legacy `ssh_annex_b` + jmuxer) |

Mode 2 = wireless live (WSU-IoT, low-rate focus). Mode 1 = wired USB CDC ECM live ([GLOSSARY.md](../../../deploy/GLOSSARY.md)).

---

## Verdict (short)

The ~**15 → ~5 → soft ~10** arc is mostly **budget and path churn**, not a single mysterious Wi‑Fi bug:

1. **~15** — early H.264 focus idle **requested** (and sometimes presented) at `fps_idle≈15` / 640×480 / ~800 kbps over TCP-ish paths.  
2. **~5** — **presented** rate collapsed when the stack over-asked (MJPEG airtime, SSH stalls, uncapped VBR, 720p/30 soft asks, UDP jitter + latency chase) or when record-preview decode was pinned near **5**.  
3. **Soft ~10** — operators **intentionally pinned** `soft_fps` / `fps_idle` to **10** as an opportunistic Mode 2 budget after soak scripts; UI treats ≥10 presented as “ok”.

**Mode 2 budget (recommend, do not apply here):** focus-live **request 10 fps** at **640×480**, **800–1200 kbps**, `buffer_count: 2`; accept presented **≳8** as operational; science `soft_fps: 10` on Wi‑Fi (pts/`*_fps.json` is truth). **Path:** keep **SSH MPEG-TS** (`preview.transport: mpegts`) for Mode 2; treat **UDP** as Mode 1 / litmus-only; **MediaMTX** later (RTSP/TCP publish + WHEP) per [mediamtx-live-backend.md](mediamtx-live-backend.md).

---

## Evidence constraints

| Source | Status |
|--------|--------|
| `deploy/bhvr-kiosk/**` code, config example, NVR-side soak scripts | Primary (tree is **untracked** in git — `git log` on this path is empty; archaeology = files + comments) |
| [deploy/NETWORK.md](../../../deploy/NETWORK.md), [deploy/GLOSSARY.md](../../../deploy/GLOSSARY.md), [deploy/bhvr-cam/offline/README.md](../../../deploy/bhvr-cam/offline/README.md) | Primary design intent |
| Agent transcript [ebe9ad12…](../../../../.cursor/projects/c-Users-admin-code-OpenEthoMaze/agent-transcripts/ebe9ad12-3589-4a66-889a-c633734e6f23/ebe9ad12-3589-4a66-889a-c633734e6f23.jsonl) (bhvr kiosk bring-up) | Primary narrative for MJPEG→H.264 and IoT tune advice |
| Live NVR `config.yaml` | **Not** in repo (gitignored / machine-local); soak scripts document what was pushed |

Sentiment note: confidence is **high** on levers and the soft-10 pin (scripts + code comments); **medium** on exact wall-clock dates of the ~15 / ~5 operator observations (no committed fps.json series in-repo).

---

## Three rates (do not conflate)

| Rate | What it is | Where |
|------|------------|--------|
| **Request / soft** | `rpicam-vid --framerate …` | `preview.fps_idle`, `record.soft_fps` |
| **Presented** | Browser `requestVideoFrameCallback` counter | [index.html](../../../deploy/bhvr-kiosk/app/templates/index.html) FPS badge (`ok` if ≥10, else `slow`) |
| **Achieved (science)** | `(n−1)/span` from `timestamps.pts` | `*_fps.json` / [fps_from_pts.py](../../../deploy/bhvr-nvr/scripts/fps_from_pts.py) |

Wireless UI copy already says resolution-only; FPS is opportunistic ([index.html](../../../deploy/bhvr-kiosk/app/templates/index.html) start modal; [main.py](../../../deploy/bhvr-kiosk/app/main.py) profile / `soft_fps` comments).

---

## Reconstructed arc

### 1) ~15 fps — request / good-path H.264 idle

- Code defaults in [preview.py](../../../deploy/bhvr-kiosk/app/preview.py): `fps_idle: int = 15`, `bitrate_kbps: 800`, `buffer_count: 1`.  
- Cam helper [live_udp_mpegts.sh](../../../deploy/bhvr-cam/scripts/live_udp_mpegts.sh) default `FPS="${5:-15}"`.  
- Early UDP smoke scripts invoke `640 480 15 800` ([`_smoke_udp.sh`](../../../deploy/bhvr-kiosk/scripts/_smoke_udp.sh), [`_smoke_udp2.sh`](../../../deploy/bhvr-kiosk/scripts/_smoke_udp2.sh), [`_trace_cam_udp.sh`](../../../deploy/bhvr-kiosk/scripts/_trace_cam_udp.sh)).  
- Transcript bring-up used SSH annex-B / TCP-listen probes at **framerate 15** / 800 kbps after leaving MJPEG.

At 480p + modest bitrate on a quiet WSU-IoT hop, **presented ≈ request** is plausible — that is the “~15” memory.

### 2) ~5 fps — presented collapse (many levers, one symptom)

Not one root cause; the ticket’s “~5” matches several documented failure modes that all show as a **slow** badge (&lt;10) or worse:

| Lever | Mechanism | Primary cite |
|-------|-----------|--------------|
| **MJPEG airtime (early)** | Per-frame JPEG on Wi‑Fi; badge swings **12→2→12** called radio/AP | Transcript advice during MJPEG era (ebe9ad12…); tune table suggested idle **8–10** |
| **Record-preview pin** | Early constants `PREVIEW_FPS_RECORD = 5` / config `fps_record: 5` | Same transcript / early config writes |
| **SSH / pipe stall** | “FD handoff to ffmpeg is stalling”; science path: “uncapped VBR over SSH/TCP was stalling ~90% of wall time” | Transcript; [main.py](../../../deploy/bhvr-kiosk/app/main.py) capture comment |
| **Over-ask** | Soft **30** / 720p / **2500 kbps** in [config.example.yaml](../../../deploy/bhvr-kiosk/config.example.yaml) while comments admit Wi‑Fi delivers less | Example YAML vs NETWORK honesty |
| **UDP + MSE chase** | Campus Wi‑Fi jitter; aggressive latency chase → empty buffer → **black** | [index.html](../../../deploy/bhvr-kiosk/app/templates/index.html) `liveBufferLatencyChasing: false` |
| **Annex-B + jmuxer** | Documented **choppy** on Zero W Wi‑Fi | [preview.py](../../../deploy/bhvr-kiosk/app/preview.py) module docstring |
| **AP / DHCP weather** | WSU-IoT flaky DHCP / apt; broadcast filtering | [NETWORK.md](../../../deploy/NETWORK.md), [offline/README.md](../../../deploy/bhvr-cam/offline/README.md) |
| **Browser player** | mpegts.js MSE vs jmuxer; badge threshold 10 | [index.html](../../../deploy/bhvr-kiosk/app/templates/index.html) |

[NETWORK.md](../../../deploy/NETWORK.md) already states four simultaneous full-quality live tiles on Wi‑Fi + Zero W is **not** an honest promise — focus-only (`max_live_full_while_recording: 1`).

### 3) Config soft ~10 — intentional Mode 2 budget

After H.264 / MPEG-TS work, NVR soak scripts **hard-set** the wireless budget to 10:

| Script | What it pins |
|--------|----------------|
| [`_deploy_softfps_udp.sh`](../../../deploy/bhvr-kiosk/scripts/_deploy_softfps_udp.sh) | `record.soft_fps = 10`, `preview.fps_idle = 10`, bitrate defaults 1200/800 |
| [`_deploy_udp_fix.sh`](../../../deploy/bhvr-kiosk/scripts/_deploy_udp_fix.sh) | Same + `transport: udp` |
| [`_restore_mpegts_preview.sh`](../../../deploy/bhvr-kiosk/scripts/_restore_mpegts_preview.sh) | `transport: mpegts` (“known-good”), `fps_idle = 10` |
| [`_deploy_wallclock_preview.sh`](../../../deploy/bhvr-kiosk/scripts/_deploy_wallclock_preview.sh) | `mpegts`, `fps_idle = 10`, `buffer_count = 2` |
| Diag / framerate fix scripts | `rpicam-vid … --framerate 10 … --bitrate 800000` |

Library defaults also encode the soft-10 philosophy for **record**: `record_settings()` uses `soft_fps` default **10** if missing ([main.py](../../../deploy/bhvr-kiosk/app/main.py)). Soft fps is explicitly **not** a session claim; pts wins.

**Important mismatch:** [config.example.yaml](../../../deploy/bhvr-kiosk/config.example.yaml) currently advertises `soft_fps: 30`, `fps_idle: 30`, 1280×720, 2500 kbps with comments that USB may ask 30 and Wi‑Fi often delivers less. That example tracks **Mode 1 aspiration**, not the Mode 2 soak pin. Do not read example-as-shipped wireless truth.

---

## Lever map (Mode 2)

```text
cam rpicam-vid  --framerate (fps_idle / soft_fps)
                --bitrate / --buffer-count / WxH / --intra / --flush
        │
        ├─ ssh_annex_b ── SSH annex-B ── jmuxer          [legacy / choppy]
        ├─ mpegts ────── SSH TCP MPEG-TS ── HTTP ── mpegts.js   [Mode 2 known-good]
        ├─ udp ───────── UDP MPEG-TS ── NVR ffmpeg ── HTTP ── mpegts.js  [WiFi fragile]
        └─ webrtc ────── UDP ── aiortc ── SDP            [not Mode 2 target]

browser presented fps  ←  MSE buffer policy (latency chasing off)
science achieved fps   ←  pts only
```

| Knob | Effect on Mode 2 | Prefer |
|------|------------------|--------|
| `preview.transport` | Reliability vs overhead | **`mpegts`** (SSH) |
| `fps_idle` / `soft_fps` | Request ceiling | **10** soft |
| Resolution | Bits/frame | **480p** for focus; 720p science only if pts ok |
| `bitrate_kbps` | Airtime / SSH stall risk | **800–1200** focus; raise only on Mode 1 |
| `buffer_count` | Encode queue depth vs latency | **2** (soak scripts); avoid chasing 1 unless latency litmus |
| Browser | Presented smoothness | mpegts.js; **no** latency chase on Wi‑Fi |
| AP/DHCP | Lease / isolation / retries | Treat as environment; USB bootstrap when IoT weather |

---

## Recommended Mode 2 fps budget

| Layer | Budget | Notes |
|-------|--------|-------|
| Focus-live **request** | **10 fps** @ 640×480 | Aligns with soak pin + UI “ok” ≥10 |
| Focus-live **presented floor** | **≳8 fps** steady | Below = treat as link/path fault, not “raise soft_fps” |
| Science **soft_fps** (Wi‑Fi) | **10** | Opportunistic; publish pts/`*_fps.json` only |
| Science soft on **Mode 1** | up to **30** | Wired; out of scope to freeze here |
| Concurrent full live | **1** focus | Already policy |

### Which path fits that budget?

| Path | Fit for Mode 2 @ ~10 fps | Role |
|------|--------------------------|------|
| **SSH MPEG-TS** | **Best interim** | TCP; restore scripts call it known-good; matches ticket-01 interim |
| **UDP MPEG-TS** | Poor as Mode 2 default | Keep for Mode 1 gadget litmus / future MediaMTX ingest shape |
| **ssh_annex_b** | Emergency only | Choppy; jmuxer |
| **aiortc WebRTC** | Do not deepen | See MediaMTX research |
| **MediaMTX** (later) | Target | Mode 2: RTSP/TCP publish + browser WHEP; soft 10 still applies until campus link proves higher |

Aligned with [research/mediamtx-live-backend.md](mediamtx-live-backend.md): Mode 2 keeps SSH MPEG-TS until MediaMTX WHEP litmus; UDP interim is Mode 1-scoped.

---

## What this ticket does *not* do

- No edits to live NVR `config.yaml`.  
- No freeze of `config.example.yaml` numbers (recommend only: example should eventually split Mode 1 vs Mode 2 profiles — separate ticket).  
- No claim that soft 10 is scientifically “validated” for pose/kpMS — Mode 2 focus is **ops monitoring**; analysis-grade rates remain Mode 1 / Mode 3 territory.

---

## Sources (primary)

1. [deploy/bhvr-kiosk/config.example.yaml](../../../deploy/bhvr-kiosk/config.example.yaml)  
2. [deploy/bhvr-kiosk/app/preview.py](../../../deploy/bhvr-kiosk/app/preview.py)  
3. [deploy/bhvr-kiosk/app/main.py](../../../deploy/bhvr-kiosk/app/main.py) (`record_settings`, SSH stall comment, preview iterators)  
4. [deploy/bhvr-kiosk/app/templates/index.html](../../../deploy/bhvr-kiosk/app/templates/index.html)  
5. [deploy/bhvr-cam/scripts/live_udp_mpegts.sh](../../../deploy/bhvr-cam/scripts/live_udp_mpegts.sh)  
6. NVR soak scripts under `deploy/bhvr-kiosk/scripts/_deploy_softfps_udp.sh`, `_restore_mpegts_preview.sh`, `_deploy_wallclock_preview.sh`, `_deploy_udp_fix.sh`, `_smoke_udp*.sh`  
7. [deploy/NETWORK.md](../../../deploy/NETWORK.md), [deploy/GLOSSARY.md](../../../deploy/GLOSSARY.md)  
8. Agent transcript ebe9ad12… (MJPEG→H.264 IoT tuning; 8–10 fps practical; 12→2→12 radio swings)  
9. Sibling research [mediamtx-live-backend.md](mediamtx-live-backend.md)  
