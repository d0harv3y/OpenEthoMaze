# Task: durable multi-cam live ingest (port map + no focus mutex)

Type: task  
Status: in progress  
Blocked by: 11  
Claimed: 2026-10-16 (USB 4× gadgets green)

## Question

_(Task — unlock simultaneous WHEP tiles + stress 1080p30×N.)_

From grill [11](11-grilling-encode-presets-menu.md):

1. **Port map:** `bhvr-camN` → UDP `15550+N` (cam0=:15550, cam1=:15551, …). Migrate cam1 off shared :15550.
2. **MediaMTX:** one path per cam id; `source: udp+mpegts://0.0.0.0:<port>`.
3. **Kiosk:** derive port from hostname/id; **stop stopping other idle previews** on focus; allow N concurrent UDP publishers.
4. **Stress config (leg A):** soft **1920×1080 @ 30** live encode (sensor-listed ceiling); measure presented/achieved on Zero + NVR load for up to 4 streams.
5. Then legs **B** (record-only) and **C** (mixed) per grill Q4.

Done when: ≥2 cams show simultaneous live tiles without stealing focus; ports match ordinal map; short note of fps/CPU/NVR load at 1080p30 soft. Presets/badge honesty still out of scope.

## Comments

### Progress 2026-10-16

**Claimed** after USB 4× ECM green (`br-bhvr`, ports 1–4).

Shipped in tree + on NVR:

1. **Port map** — `cam_udp_port("bhvr-camN")` → `15550+N` (`deploy/bhvr-kiosk/app/preview.py`). Cam1 migrated off shared `:15550` → `:15551`.
2. **MediaMTX** — paths `bhvr-cam0`…`bhvr-cam7` with matching UDP sources (`deploy/bhvr-nvr/mediamtx/mediamtx.yml`); restarted on NVR.
3. **Kiosk** — no longer stops other idle publishers on focus; UI allows N concurrent live tiles (`main.py` + `index.html`).
4. **Litmus (API):** `preview_idle=["bhvr-cam0","bhvr-cam1"]` with ports 15550/15551; both cams keep `rpicam-vid`+`ffmpeg` up; WHEP OPTIONS 204. Script: `deploy/bhvr-nvr/scripts/_litmus_multicam_whep.sh`.
5. **Ops note:** pushed static `~/bin/ffmpeg` + `live_udp_mpegts.sh` to cam0/2/3 (were missing on cam0).

### Stress leg A — 2026-10-16 (live-only 1080p30×4)

Config on NVR (`~/bhvr-kiosk/config.yaml`): soft **1920×1080 @ 30**, bitrate 4000 kbps, `sensor_mode=1920:1080` all cams. Script: `deploy/bhvr-nvr/scripts/_stress_leg_a_1080p30.sh`. Log: `/tmp/stress_leg_a_20261016T162744Z.txt`.

| Layer | Result |
|-------|--------|
| Soft ask | 1920×1080 @ 30 (OV5647 mode lists 1920×1080 / 32.8) |
| Concurrent | all 4 in `preview_idle`; ports 15550–15553; `--mode 1920:1080:10:P` |
| **Achieved encode** (cam2, 8s file → NVR ffmpeg count) | **≈14.0 fps** (112 frames / 8 s) — soft 30 not met; same ballpark as Mode 1 720p pts ceiling (~15) |
| Cam CPU / temp (while 4× live) | rpicam ~37–39%, ffmpeg ~4%; 64–69 °C; load ~0.8–1.5 |
| NVR (4 cores) | load ~10–11; vmstat ~80% user / ~1–6% idle; Chromium ~65% (4 WHEP tiles); MediaMTX ~14%; RAM fine (~1.3 / 7.6 Gi) |
| Baseline (operator, pre-stress) | 720p tiles ~20 presented fps ×4 |

**Read:** Ceiling is still Zero encode, not MediaMTX/USB. Soft 1080p30×4 is survivable (cams stay up; NVR CPU hot mainly from Chromium decode). Honest Mode 1 budget stays ~15 fps class; do not advertise soft 30 as achieved.

Operator: hard-refresh — tiles should now be 1080p soft; note **presented** fps on badges (compare to ~14 achieved).

### Stress leg B — 2026-10-16 (record-only 1080p30×4)

No live tiles. Science session `1080p` profile (new `PROFILE_GEOM` entry), `record.soft_fps=30`, bitrate 4000, sensor `1920:1080`. Script: `_stress_leg_b_record_only.sh`. Session: `/data/bhvr/sub-stress-leg-b/ses-20261016T165140Z` (SSD `/media/admin/random/bhvr` was **unmounted** — fell back to `/data/bhvr`).

| Cam | Achieved pts fps | NVR h264 bytes | Notes |
|-----|------------------|----------------|-------|
| cam0 | **29.35** | ~39 MB | dt median 33.33 ms |
| cam1 | **29.32** | ~38 MB | |
| cam2 | **29.30** | ~38 MB | |
| cam3 | — | 25 KB stuck | SSH died mid-run (`Connection refused` / timeout); gadget later reappeared |

Cam CPU while healthy: rpicam ~50–53%, ~68 °C. NVR during record (no WHEP tiles): load fell ~12→~6; idle ~60%; Chromium still ~100% (kiosk open); SSH capture procs light.

**Read vs leg A:** Record-only **hits soft ~30** @ 1080p on Zero (SSH annex-B + `--save-pts`, no cam-side ffmpeg MPEG-TS). Live WHEP path (~14 achieved) is limited by **mux/ingest/decode stack**, not raw encode. cam3 dropout under 4× USB record is a hub/stability flag for leg C.

Still open: leg **C** (mixed live+record).

### WHEP path investigation — 2026-10-16

Write-up: [research/whep-path-optimizations.md](../research/whep-path-optimizations.md).

Headline: record-only ≈29 fps vs live ≈14 is mostly **cam-side ffmpeg MPEG-TS remux + WHEP chain**, not sensor encode. Current `rpicam-apps` has **`libav:0`** — no native MPEG-TS. Best next prototype: **O1a NVR-side remux** (annex-B off cam like record). SSD remount script: `deploy/bhvr-nvr/scripts/remount_ssd.sh`.

### O1a prototype live — 2026-10-16

- `preview.whep_ingest: nvr_annexb` on NVR (SSD remounted; `data_root=/media/admin/random/bhvr`).
- Litmus: cams run **rpicam only** (no cam ffmpeg); NVR remux → MediaMTX; WHEP 204.
- Rollback: set `whep_ingest: cam_mpegts` and restart kiosk.

### Native RTSP litmus (one cam) — 2026-10-16

- Enabled MediaMTX **RTSP :8554**; fixed orphan mediamtx crash-loop.
- `mpv` missing → **ffplay** + ffmpeg probes. Details: [whep-path-optimizations.md](../research/whep-path-optimizations.md) § Native RTSP litmus.
- **Verdict:** RTSP read OK @ 1080p; native path still ~**18 fps** into/through MediaMTX (copy and decode) — not leg-B 29. Chromium skip alone ≠ soft-30.

### Soft-30 unlock — `buffer_count` (2026-10-16)

- Local pts matrix: `--flush --buffer-count 2` → **~15 fps**; `--buffer-count 6` → **~28 fps**. Record never passed `--buffer-count` (rpicam default) → leg B ~29.
- NVR `~/bhvr-kiosk/config.yaml` set `preview.buffer_count: 6`; example yaml updated. Operator: one-cam WHEP ~1080p30 low latency.

### Stress leg A re-run — 2026-10-16 (buf=6, O1a)

Log: `/tmp/stress_leg_a_20261016T194920Z.txt`. Soft 1920×1080@30, `buffer_count: 6`, `whep_ingest: nvr_annexb`, all 4 `whep/start`. Script now keeps buf≥6 + RTSP `-c copy` wall_fps.

| Cam | SSH / encode | RTSP copy wall_fps (8s) | Notes |
|-----|--------------|-------------------------|-------|
| cam0 | rpicam `--buffer-count 6`, ~57% CPU, 71°C | **23.1** | ffmpeg=0 on cam |
| cam1 | same, ~56%, 71°C | **24.4** | |
| cam2 | same, ~57%, 56°C | **25.6** | |
| cam3 | **SSH timeout / no route** | FAIL | USB hub flake (same class as leg B) |

NVR while 4× API-live (Chromium tiles likely open): load ~9–12; Chromium ~94%+76%; MediaMTX ~36%; vmstat idle ~8–14%. RAM fine.

**Read vs first leg A (~14 fps @ buf=2):** healthy cams **~23–26 wall_fps** into MediaMTX — big step, not yet soft 30×4. Ceiling now looks **NVR remux/USB + Chromium**, not encode buffers. cam3 still a hub stability flag. Operator: note **presented** tile fps with 1 vs 4 tiles.

### Native mpv 2×2 spike — 2026-10-16

Scripts: `deploy/bhvr-nvr/scripts/_spike_mpv_grid.sh` / `_spike_mpv_grid_stop.sh`.

- Starts all 4 `whep/start` (same ingest), then **mpv** RTSP tiles on labwc (`1024×600` → 512×300 quadrants).
- Deployed/run on NVR: 4 RTSP ready; 4 mpv PIDs started.
- Operator: compare feel/latency/smoothness vs Chromium WHEP; stop with `_spike_mpv_grid_stop.sh`.
- **Outcome:** felt as bad as WHEP; windows **exited ~4s** — not intentional. Logs: software decode `VO 1920x1080`, then `rtsp: End of file` on all four (publish/path died under 4× full-res soft decode). Native tiles alone ≠ win without lower live ask or HW decode.

### Design decision — live scale on NVR (2026-10-16)

Operator: prefer **one cam encode → NVR fan-out** (science raw + scaled live); **no** dual encode on Zero W. Spec note: [whep-path-optimizations.md](../research/whep-path-optimizations.md) § Design choice.

### Fan-out litmus — 2026-10-16

Scripts: `_litmus_fanout_onecam.sh`, `_litmus_fanout_x4.sh` (TCP annex-B → NVR: copy science `.h264` + `scale=640:360,fps=15` libx264 → MediaMTX).

**One-cam (bhvr-cam0):** science **pts_fps ≈ 29.05** PASS; live RTSP **640×360 @ 15/1**, wall_fps ≈ **14.2**.

**Fan-out design (post NVR reboot 2026-10-16):** one cam encode → NVR Stage A (bitstream copy science + localhost MPEG-TS) → Stage B (scale 480×270@8 → MediaMTX). No dual encode on Zero. Script: `_litmus_fanout_x4.sh`.

| Cam | Science pts_fps | Live wall_fps (≥6) | Notes |
|-----|-----------------|--------------------|-------|
| cam0 | **≈29.5** PASS | **≈7.4** PASS | stable |
| cam1 | **≈29.4** PASS | **≈7.6** PASS | stable |
| cam2 | **≈29.6** PASS | **≈7.2** PASS | was flaky earlier; green after reboot |
| cam3 | FAIL (pts empty / 0 bytes) | FAIL | USB/SSH flake; gadget present but encode dies |

**Verdict:** software path is **3/4 green** under ×4 (science soft ~30 + scaled live). **4/4 blocked by cam3 hardware/hub**, not NVR scale design. Do not restart MediaMTX mid-litmus (drops binds). Board/cable swap for cam3 still the fix for full green.

### Port-swap isolation — 2026-10-19

Operator moved which Zero sits on which hub port. Identity = hostname on SD (unchanged). Litmus: `_litmus_fanout_x4.sh`.

| Cam id | Science (pre-swap) | Science (post-swap) |
|--------|--------------------|---------------------|
| bhvr-cam0 | PASS | **FAIL** (0 bytes / pts empty) |
| bhvr-cam1 | PASS | PASS ≈29.6 |
| bhvr-cam2 | PASS | PASS ≈29.5 |
| bhvr-cam3 | **FAIL** | **PASS ≈29.5** |

**Read:** flake **followed the hub port** (or the cable left on that port), **not** the Zero that was named cam3. The former cam3 board encodes fine on a different port. Next: mark/replace that physical hub port or its cable; optional second swap to confirm.

### ×3 load test (cam2 unplugged) — 2026-10-19

Hub leaf **1-1.1.1 empty**; active cam0+cam1+cam3 (cam0 = Zero that failed on “bad” port at ×4).

| Cam | Science bytes | Dropout (0-byte) signature? |
|-----|---------------|-----------------------------|
| cam0 (prior bad-port Zero) | **~48 MB** | **no** — SSH still up after |
| cam1 | ~50 MB | no |
| cam3 | ~54 MB | no |

(pts_fps litmus said ~3–5 — measurement/span quirk; not the classic 0-byte kill.)

**Read:** at **3 cams** the previously failing port’s Zero **stays alive**. Points to **hub aggregate power/bandwidth under ×4**, not a hard-dead receptacle. Still prefer a better-powered hub / avoid that leaf under full load; not “replace one Zero.”

### Battery-backed cams ×4 — 2026-10-19

Operator installed packs on each Zero (~2 h claim); USB mostly data. All 4 hub leaves occupied.

| Cam | Science pts_fps | Notes |
|-----|-----------------|-------|
| cam0–3 | **≈29.5 PASS** all four | no 0-byte dropout; SSH still up after |
| live ×4 | BELOW / RTSP flaky | MediaMTX bind 3/4 mid-run; scale path still soft — separate from power |

**Read:** **hub VBUS was the ×4 killer.** Batteries unlock science soft-30×4 on the current hub. Keep the powered-hub PO for sustained bus-powered ops; live scale×4 still needs a follow-up.

### Live-ask ladder on NVR Pi 4 (battery ×4) — 2026-10-19

Script: `_litmus_fanout_live_ladder.sh`. Decoupled fan-out; science gate ≥25; live = RTSP wall_fps vs ask.

| Rung | Ask | sci PASS | min wall_fps | Verdict |
|------|-----|----------|--------------|---------|
| 1 | 320×180@5 | 4/4 | **1.67** | LIVE_DEAD |
| 2 | 320×180@10 | 4/4 | 2.50 | LIVE_DEAD |
| 3 | 480×270@5 | 4/4 | 1.00 | LIVE_DEAD |
| 4 | 480×270@8 | 4/4 | 2.67 | LIVE_DEAD |
| 5 | 480×270@15 | 4/4 | 4.50 | LIVE_DEAD |
| 6 | 640×360@8 | 4/4 | 2.17 | LIVE_DEAD |
| 7 | 640×360@15 | 4/4 | **5.33** | LIVE_DEAD |
| 8 | 960×540@10 | 4/4 | 0.67 | LIVE_DEAD |
| 9 | 1280×720@10 | 3/4 | 3.67 | **SCIENCE_HURT** |

**Read:** Output size barely moves live wall — **soft-decode of 1080p30×4 on Pi 4** is the ceiling, not libx264 of the tiny tile. Science stays green until a huge live ask (720p scale×4) finally backpressures. Wiggle room for “nice tiles” on this NVR alone: **none** at ×4 without changing architecture or hardware.

**Hardware to close acquisition→display gap** (science stays one HW encode on Zero; live needs cheap tiles):

1. **Best fit:** small **x86 NVR/sidecar** with **Quick Sync / NVDEC** (NUC / mini-PC) — HW decode 4×1080 + scale/encode tiles; Pi 4 stays DAQ/USB/MediaMTX control or moves off box.
2. **Alt:** **Jetson**-class ARM with HW decode (same job as Quick Sync).
3. **Not a fix:** Pi 5 alone (no H.264 HW decode) or hoping Pi 4 V4L2 M2M does reliable 4×1080p30 (unproven here; prior HW probe failed).
4. **Display-side only:** full-res copy to players with HW decode×4 — fails on Chromium/mpv soft path we already tried unless the panel SoC can HW-decode four 1080p streams.

## Comments
