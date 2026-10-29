# Research: Mode 1 720p ~15 fps ceiling (Zero W + OV5647)

**Ticket:** [.scratch/bhvr-fleet-modes/issues/10-research-mode1-720p-fps-ceiling.md](../issues/10-research-mode1-720p-fps-ceiling.md)  
**Date:** 2026-10-14  
**Host:** `bhvr-cam1` (Pi Zero W, BCM2835 ARMv6, OV5647), USB to NVR, focus via MediaMTX WHEP

## Question

Kiosk requests **1280×720 @ soft 30**; tile presents **~15 fps**. Where is the ceiling? What honest Mode 1 budget should we publish?

## Acronyms

| Term | Meaning |
|------|---------|
| Soft fps | `rpicam-vid --framerate` request only |
| Achieved fps | `(n−1)/span` from `rpicam-vid --save-pts` |
| Presented fps | Browser `requestVideoFrameCallback` badge |

## Verdict (short)

**Ceiling is on the cam encode path, not MediaMTX / WHEP / USB.**

At 720p with soft 30, **achieved ≈ 15.1–15.6 fps** with rock-stable `med_dt ≈ 66.7 ms` (exactly 1/15 s). The browser is telling the truth. Fixed `--shutter`/`--gain` did **not** unlock 30 → not a simple AE shutter trap. Sensor mode for 720p is **1920×1080 RAW** (max listed 32.81 fps); Zero W ISP/encode on one core settles at ~15. **480p** reaches **~22–23 achieved** (closer to soft 30). **`avahi-daemon` often burns 25–70% CPU** on this cam — strong follow-on lever (needs sudo to stop); not yet A/B’d.

**Recommend Mode 1 focus budget:** keep **720p @ soft 15** (honest, matches achieved) **or** **480p @ soft 30** if you want higher presented fps. Stop advertising soft 30 @ 720p on Zero+OV5647.

---

## Evidence (cam1, 5 s `--save-pts` runs)

| Trial | Soft request | Sensor mode selected | Achieved fps | med_dt |
|-------|--------------|----------------------|--------------|--------|
| 1280×720 @ 30 | 30 | 1920×1080 | **15.46** | 66.7 ms |
| 1280×720 @ 30 + `--mode 1296:972` | 30 | 1296×972 | **17.37** | 66.7 ms |
| 640×480 @ 30 | 30 | 640×480 | **23.08** | 33.3 ms |
| 1280×720 @ 15 | 15 | 1920×1080 | **12.69** | 66.7 ms |
| 1280×720 @ 30 + shutter 8–15 ms | 30 | 1920×1080 | **~15.1–15.3** | 66.7 ms |
| 1280×720 @ 20 | 20 | 1920×1080 | **13.26** | 99.9 ms |

`rpicam-vid --list-cameras` OV5647 modes: 640×480@62.5, 1296×972@46.3, 1920×1080@32.8, 2592×1944@15.6.

During 720p30 encode: **1 CPU**, load ~2.6; `rpicam-vid` ~15–25% while **`avahi-daemon` ~25–70%** (could not stop without sudo).

Kiosk config at test: `fps_idle: 30`, `transport: whep`, 2500 kbps. MediaMTX WHEP already soft-passed for latency; presented ~15 matches pts.

Scripts: `deploy/bhvr-nvr/scripts/_dig_fps_*.sh`.

---

## What we ruled out

| Hypothesis | Result |
|------------|--------|
| MediaMTX / WHEP / mpegts.js drop | No — pts on cam already ~15 before network |
| USB gadget bandwidth | No — local file encode same ~15 |
| Soft 30 not applied | No — logs show `framerate: 30`, mode pick for 30 |
| AE long shutter only | Unlikely — fixed shutter/gain unchanged 66.7 ms cadence |

---

## Recommended actions

1. **Honest config:** Mode 1 `preview.fps_idle: 15` at 1280×720 (or document “soft 30 → expect ~15 achieved”).  
2. **Optional UI path:** 480p focus when operator wants higher presented fps.  
3. **Cam hygiene:** ~~disable avahi~~ — confirmed: cam1 felt more stable with avahi off (~44% CPU freed). Baked into `firstboot/99-bhvr-cam.sh` (`disable --now` service + socket).  
4. Do **not** spend more time tuning MediaMTX for fps.

## Confidence

| Claim | Confidence |
|-------|------------|
| Achieved encode ≈ 15 @ 720p soft 30 | **High** (pts) |
| Not MediaMTX/USB | **High** |
| Zero ISP + 1080p RAW path is the structural limit | **Medium–high** |
| avahi is a large aggravator | **Medium** (CPU samples; stop not yet measured) |
