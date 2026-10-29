# Bhvr fleet modes — wayfinder map

Labels: `wayfinder:map`

## Destination

A clear **operating model** for the kiosk + NVR + cam fleet with **three modes** (Mode 1 wired live primary), plus a proven **wired bootstrap**: after Imager + arm, a cam on USB reaches the kiosk with **MQTT roster + SSH** (no SD pulls for routine maintenance). Mode 1/2 **live pipeline** direction is **long-term smoothness** (MediaMTX / WebRTC-class), not annex-B. Mode 3 exists as **spec only** on this map.

## Notes

- Domain: deploy/bhvr-cam, bhvr-nvr, bhvr-kiosk; WSU-IoT campus WiFi; USB CDC ECM gadget.
- Tracker: local-markdown (`.scratch/bhvr-fleet-modes/`).
- Skills: grilling, domain-modeling; research tickets → research skill.
- Prefer dual-path: USB for bring-up / Mode 1 / package push; WiFi for Mode 2/3 + NVR name (mDNS `.local` ok).
- Do not treat `NETWORK.md` overnight-WiFi-primary as truth until updated from this map.
- Glossary: [deploy/GLOSSARY.md](../../deploy/GLOSSARY.md) (fleet); analysis vocab stays under `docs/vocab/`.

## Decisions so far

- [Research MediaMTX (and peers) for Mode 1 + Mode 2 live](issues/01-research-mediamtx-live-backend.md): MediaMTX on NVR; cams publish RTSP/UDP-MPEG-TS; browser WHEP; interim Mode 1 UDP MPEG-TS yes; Mode 2 SSH MPEG-TS until WHEP; no cam-local rpiCamera / no deepen aiortc. Write-up: [research/mediamtx-live-backend.md](research/mediamtx-live-backend.md).
- [Research Mode 2 wireless focus-live fps regression](issues/02-research-wireless-fps-regression.md): ~15→~5→soft~10 is budget/path churn not one Wi‑Fi mystery; recommend Mode 2 focus **10 fps @ 480p** over SSH MPEG-TS; config not changed. Write-up: [research/wireless-fps-regression.md](research/wireless-fps-regression.md).
- [Grill interim live bridge vs jump to MediaMTX](issues/07-grilling-interim-live-bridge.md): interim yes — ffmpeg on cam1 + Mode 1 UDP MPEG-TS verify before MediaMTX; annex-B emergency only.
- [Grill MediaMTX cutover (sibling WHEP path)](issues/08-grilling-mediamtx-cutover.md): **resolved** — sibling `whep`; UDP ingest :15550 exclusive; idle-only; kiosk-first; path=MQTT id; no auth v1.
- [Task MediaMTX sibling + whep](issues/09-task-mediamtx-sibling-whep.md): **resolved** — Mode 1 default `whep`; operator: less latency, slightly stabler fps, still ~15; `udp` fallback kept.
- [Research Mode 1 720p fps ceiling](issues/10-research-mode1-720p-fps-ceiling.md): **resolved** — achieved pts ≈15.5 @ 720p soft 30 (Zero+OV5647); not MediaMTX. Budget: soft 15 @ 720p or 480p@30. Write-up: [research/mode1-720p-fps-ceiling.md](research/mode1-720p-fps-ceiling.md).
- [Task multi-cam live ingest](issues/12-task-multicam-live-ingest.md): **in progress** — multi-tile WHEP shipped; leg A live 1080p30×4 ≈14 fps; leg B record-only ≈29.3 pts fps (cam3 USB drop); leg C open; live ladder soft-decode ceiling on Pi4.
- [Grill encode presets](issues/11-grilling-encode-presets-menu.md): **resolved 2026-10-19** — 4:3 Standard/Lite × fps; kill sensor menu; idle Lite@10; display decimation; no focus v0.
- [Task science-ask prototype](issues/13-task-science-ask-prototype.md): **in progress** — kiosk encode_ask + modal chips + honesty badge.
- [Grill Mode 2 wireless](issues/14-grilling-mode2-wireless.md): **resolved** — litmus A (SSH→WHEP) vs B (SSH MPEG-TS); stopwatch ≤1s; auto Mode2 when `br-bhvr` down.

### Settled in charting (grill), not yet their own closed tickets

- Bootstrap pass = MQTT roster + SSH (not focus-live fps).
- Auto: USB plugged → Mode 1 preference; unplug → wireless; kiosk per-cam override.
- Mode 3 = thin spec only (no local-store build on this map).
- Packages: bake `debs/` on new cards **and** USB-push for existing cams (e.g. cam1).

## Not yet specified

- Science tee into MediaMTX while recording (deferred; v1 = idle-only).
- `bhvr-mediamtx` systemd enable (needs sudo TTY on NVR).
- Cam1 `avahi-daemon` CPU hog — sudo disable + remeasure 720p pts (see [10](issues/10-research-mode1-720p-fps-ceiling.md)).
- Hub power / multi-cam USB topology limits.
- WSU-IoT MAC allowlist / IT process (if required).
- cam0 identity and first wired bootstrap instance.

## Out of scope

- Full Mode 3 local-store + NVR backup implementation.
- Pose / kpMS / NeuroConv / NWB / DANDI.
- Replacing Mosquitto roster with another discovery bus (unless MediaMTX research forces it).
