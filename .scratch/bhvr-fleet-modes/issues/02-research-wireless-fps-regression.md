# Research Mode 2 wireless focus-live fps regression

Type: research  
Status: resolved  
Blocked by:

## Question

Why did wireless focus-live on WSU-IoT move roughly **~15 fps → ~5 fps → config soft ~10**, across earlier bhvr-kiosk tests?

Identify likely levers (transport, `soft_fps` / `fps_idle`, bitrate, buffer, AP/DHCP, SSH vs UDP, browser player). Recommend a **Mode 2 fps budget** and which path (SSH MPEG-TS vs UDP vs future MediaMTX) fits that budget. Do not change live config in this ticket — recommend only.

## Comments

### Answer draft (2026-10-14)

**Arc:** ~15 was early H.264 idle *request*/good-path present; ~5 was presented collapse (MJPEG airtime / SSH stalls / over-ask 30 / UDP+MSE chase / annex-B chop); soft ~10 is the intentional Mode 2 pin in NVR soak scripts (`soft_fps`/`fps_idle`=10).

**Mode 2 budget (recommend only):** focus **10 fps @ 480p**, 800–1200 kbps, `buffer_count` 2; presented floor ≳8; science soft_fps 10 on Wi‑Fi (pts truth). **Path:** SSH MPEG-TS interim; UDP not Mode 2 default; MediaMTX later.

Full write-up: [research/wireless-fps-regression.md](../research/wireless-fps-regression.md)

## Answer

**Arc:** ~15 was early idle *request*/good path; ~5 was **presented** collapse (transport/over-ask/UDP+MSE/annex-B); soft ~10 is an intentional Mode 2 pin in soak config — not a single AP mystery.

**Mode 2 budget (recommend only):** focus **10 fps @ 640×480**, 800–1200 kbps, `buffer_count: 2`; presented floor ≳8; science `soft_fps: 10` on Wi‑Fi (pts truth). **Path:** SSH MPEG-TS interim; UDP for Mode 1/litmus; MediaMTX later.

**Evidence:** [research/wireless-fps-regression.md](../research/wireless-fps-regression.md) (via [Wireless FPS regression research](c81e44da-6902-449f-a303-8f2268bc17eb)). Live config untouched.
