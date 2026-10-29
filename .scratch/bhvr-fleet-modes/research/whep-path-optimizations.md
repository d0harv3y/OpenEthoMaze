# Investigation: WHEP live path bottlenecks vs record-only

**Date:** 2026-10-16  
**Context:** Stress legs A/B on issue [12](../issues/12-task-multicam-live-ingest.md)  
**Question:** Soft 1080p30 live WHEP got ≈14 fps achieved / worse latency; record-only hit ≈29.3 pts fps. Where can the WHEP path improve?

## Path comparison (same Zero + OV5647 + USB)

| Stage | Leg A live WHEP | Leg B record-only |
|-------|-----------------|-------------------|
| Sensor / encode | `rpicam-vid` HW H.264 1920×1080 soft 30 | same |
| Cam remux | **`ffmpeg` annex-B → MPEG-TS** (`live_udp_mpegts.sh`) | **none** (stdout annex-B) |
| Cam → NVR | UDP MPEG-TS → `192.168.7.1:15550+N` | SSH stdout pipe |
| NVR ingest | MediaMTX `udp+mpegts` path | kiosk writer → `*_video.h264` |
| Browser | WebRTC **WHEP** (Chromium decode ×N) | n/a |
| Achieved | **≈14 fps** (8s file count) | **≈29.3 pts fps** (cam0–2) |

So the Zero **can** sustain ~30 @ 1080p when the pipe is annex-B → SSH. The live stack adds **cam ffmpeg mux + UDP + MediaMTX protocol conversion + browser WebRTC decode**. Latency feel tracks that conversion chain (operator: worse than 720p).

## Bottleneck hypotheses (ranked)

### 1. Cam-side `ffmpeg` MPEG-TS remux (high confidence)

`live_udp_mpegts.sh` always inserts:

`rpicam-vid -o - | ffmpeg -f h264 -i pipe:0 -c copy -f mpegts udp://…`

Evidence:

- Record path omits this and nearly hits soft 30.
- Live logs show ffmpeg `probesize 32` / PPS errors at start; SIGPIPE when mux dies (`failed to write output bytes`).
- Even at ~4% CPU, **pipe backpressure** stalls HW encode (wall fps collapse).

### 2. MediaMTX UDP-MPEG-TS → WebRTC conversion (medium)

MediaMTX must demux TS, re-packetize to RTP/WebRTC. Extra latency vs raw annex-B archive; CPU on NVR was ~14% for 4 paths (survivable) but adds glass-to-glass delay.

### 3. Browser decode ×4 at 1080p (medium for NVR load / latency feel)

Leg A: Chromium ~65% CPU, NVR load ~10–11, idle ~1–6%. Leg B (no tiles): idle ~60%, load ~6 — Chromium still hungry if kiosk left open. Four 1080p WHEP tiles are an operator-UI cost, not a cam encode cost.

### 4. Soft ask / bitrate (low for “why 14 vs 29”)

Same soft 30 + 4 Mbps both legs. Bitrate/GOP are not the A/B discriminator.

### 5. USB hub (cam3 flake only)

cam3 dropped mid–leg B under 4× SSH H.264; gadget later re-enumerated. Separate from the 14 fps ceiling on healthy cams.

## Probe note (cam1, 2026-10-16)

```
rpicam-apps capabilities: egl:0 qt:0 drm:1 libav:0
codec args include libav — but this build has libav disabled
```

So **native rpicam MPEG-TS/RTSP (libav) is unavailable** on current cam images without rebuilding/replacing `rpicam-apps`.

## Optimization opportunities

| # | Change | Expected win | Risk / cost | Effort |
|---|--------|--------------|-------------|--------|
| **O1a** | **NVR-side remux** — cam sends raw annex-B (like record); NVR `ffmpeg` wraps MPEG-TS → MediaMTX | Move mux CPU off Zero; should approach record-only encode fps; less SIGPIPE on cam | Need a durable annex-B transport (UDP/TCP/SSH); NVR runs N ffmpeg bridges | M — **best bet without new cam packages** |
| **O1b** | Ship **libav-enabled** `rpicam-apps` on cams → `--codec libav --libav-format mpegts` | Same as O1a without NVR bridge | Image/offline-deb work; armv6 build | L |
| **O2** | **RTSP publish** from cam ffmpeg into MediaMTX | Stabler than UDP-TS; Mode 2 later | Still cam ffmpeg (same class as today) | M |
| **O3** | Soften live ask: **720p @ 15** or **480p @ 30** for multi-tile | Presented fps / latency | Product messaging | S |
| **O4** | **Two-tier live**: grid low-res; focus full soft | NVR Chromium + USB | UI | M |
| **O5** | Fix mux knobs: drop `probesize 32` / `analyzeduration 0` | Fewer black starts | Small | S |
| **O6** | MediaMTX WebRTC tuning | Latency feel | Weak if cam already at 14 fps | S |
| **O7** | Science tee: one encode → archive + live | Leg C without 2nd encode | pts/ownership | L |

**Not recommended on Zero:** second encode, cam-local MediaMTX `rpiCamera`, deepening aiortc.

## Suggested order

1. **O5** (safe).  
2. Prototype **O1a** (annex-B to NVR, remux there) — litmus vs today’s UDP-TS.  
3. Product **O3/O4** for honest multi-tile.  
4. Optional **O1b** if offline bake can ship libav rpicam.  
5. Leg C after cam3 USB + O1a decision.

## Litmus for any optimization

- Same soft ask; measure **achieved** (pts or timed H.264 frames) and **presented** tile fps + subjective latency.  
- Target: live achieved within ~5 fps of record-only on one cam before claiming mux fixed.

## Prototype O1a — shipped 2026-10-16

Config: `preview.whep_ingest: nvr_annexb` (rollback: `cam_mpegts`).

Code: `cam_live_annexb_remote` + `nvr_ffmpeg_annexb_to_mediamtx_udp` in `preview.py`; kiosk `_start_cam_annexb_nvr_remux` pipes SSH stdout → NVR ffmpeg → `udp://127.0.0.1:15550+N`.

**API litmus** (`_litmus_o1a_annexb_whep.sh`): cam0+cam1 start OK; **cam `rpicam=1 ffmpeg=0`**; NVR remux ffmpeg ×2; WHEP OPTIONS 204. Remux warns “Timestamps unset” (annex-B) — expected with genpts.

Operator: hard-refresh kiosk; compare presented fps / latency vs pre-O1a cam_mpegts at same soft 1080p30.

### Operator feedback (same day)

O1a **did not feel better** — “maybe a little worse.” Interpretation: we removed cam ffmpeg but **added SSH** (encrypt + buffer) as the annex-B hop. Glass-to-glass feel is still dominated by **MediaMTX MPEG-TS→WebRTC + Chromium ×N**, which O1a does not touch. Cam CPU win ≠ latency win.

**Revised ranking for latency feel:** (1) browser WebRTC decode / WHEP conversion, (2) soft ask too high (1080p30), (3) publish mux/transport. RTSP publish (O2) may help Mode 2 stability more than Mode 1 latency. Native (non-browser) tile player remains the big architectural lever if WHEP plateaus.

## Native RTSP litmus (mpv/ffplay) — 2026-10-16

**Goal:** one cam, MediaMTX **RTSP read** → native player (vs Chromium WHEP). Scripts: `deploy/bhvr-nvr/scripts/_litmus_mpv_rtsp_onecam.sh`, `_run_rtsp_decode_probe.sh`, `_run_rtsp_hw_probe.sh`.

**Prep:**

- NVR `mediamtx.yml`: `rtsp: true`, `rtspAddress: :8554` (also in repo `deploy/bhvr-nvr/mediamtx/mediamtx.yml`).
- Cleared orphan `mediamtx` holding UDP/WHEP ports while `bhvr-mediamtx` crash-looped (~31k restarts).
- **`mpv` not installed** on NVR — used **ffplay** (same native class). Install: `sudo apt install -y mpv`.

**Results (bhvr-cam0, soft 1080p30, `whep_ingest=nvr_annexb`):**

| Check | Result |
|-------|--------|
| RTSP DESCRIBE once path hot | OK — `h264,1920,1080,30/1` |
| WHEP OPTIONS | 204 (unchanged sibling) |
| ffmpeg **decode** → null (~12–15 s) | steady ~**17–18 fps**, speed ~**0.66–0.71×** (falls behind realtime) |
| ffmpeg **`-c copy`** → null (no decode) | same ballpark ~**18 fps** / speed ~**0.72×** |
| `-hwaccel auto` | tried **vulkan**, init failed → software fallback |
| ffplay on-screen 8 s (`DISPLAY=:0`) | session opened/closed in journal (operator: confirm window on touchscreen) |

**Read:** RTSP egress from MediaMTX **works**. Skipping Chromium does **not** by itself unlock soft 30 — even packet-copy off RTSP sits ~18 fps class, so **O1a SSH annex-B → remux → MediaMTX** is still short of leg B’s ~29 pts fps. Native tiles remain useful for **latency feel / CPU** once publish rate is honest; next native step wants **mpv + working Pi HW decode** (vulkan failed here), not more WHEP tuning.

**Ops note:** after preview restart, wait for “stream is available” before RTSP clients (early DESCRIBE → 404).

## Unlock soft ~30: `buffer_count` (2026-10-16)

Transport experiments (TCP annex-B vs SSH O1a) still sat ~15–18 fps **into** MediaMTX. Isolation matrix on cam0 local file:

| Tag | knobs | pts fps |
|-----|-------|---------|
| G | `--flush --buffer-count 2` (live config default) | **~15** |
| F | `--flush --buffer-count 4` | **~26** |
| H | `--flush --buffer-count 6` | **~28** |
| leg B record | `--flush`, **no** `--buffer-count` (rpicam default) | **~29** |

So the soft-30 blocker was **not** primarily WHEP/SSH/TCP — live preview pinned `buffer_count: 2`, which halves OV5647 1080p encode under `--flush`. Record omitted the flag → default buffers → ~30.

**Action:** set `preview.buffer_count: 6` (NVR `config.yaml` + `config.example.yaml`). Re-measure RTSP `-c copy` wall fps / mpv drops after kiosk restart + `whep/start`.

**Leg A re-run (buf=6, O1a, 4× start):** healthy cams RTSP copy **wall_fps ≈23–26** (was ≈14 @ buf=2). cam3 USB down. Soft 30×4 still not met; next levers = multi-tile ask / native tiles / hub, not more buffer.

## Design choice: one encode → NVR live scale (2026-10-16)

**Reject** dual encode on Pi Zero W (untrusted under load / leg C).

**Target:**

```text
Cam:  rpicam-vid HW H.264  (science soft ask, e.g. 1080p30)  annex-B
        │
        │  durable hop (prefer USB TCP/UDP; SSH OK for Mode 2)
        ▼
NVR:  tee / fan-out
        ├─ science writer → *_video.h264 + pts   (raw / full soft)
        └─ ffmpeg scale+fps (e.g. 640×360@15) → MPEG-TS → MediaMTX
              └─ kiosk read: WHEP and/or native RTSP tiles
```

- **One** HW encode per cam (same ownership as today’s record pipe).
- Live is **spatially and/or temporally downsampled on the NVR** only.
- Idle preview without a session: still one encode at science soft *or* a dedicated lower live ask — but never two concurrent encodes on the Zero.
- Native tiles remain optional once the live bitstream is small; they are not the primary unlock.

**Litmus 2026-10-16:** one-cam **pts≈29** + live **640×360@~14 wall_fps** PASS. ×4: cam0/1 same class PASS; cam2/3 USB/path FAIL (cam3 board-swap candidate). Scripts: `_litmus_fanout_onecam.sh`, `_litmus_fanout_x4.sh`.
