# Grill: Mode 2 wireless live (same philosophies as science-ask)

Type: grilling  
Status: resolved (litmus A/B next)  
Blocked by: 11, 13  
Unblocks: Mode 2 cutover task (after litmus winner)

## Question

Dial Mode 2 (WSU-IoT, USB unplugged) with the same split as Mode 1: **science ask** (cam encode) vs **live display** (kiosk paint), one encode, honest badges. Stream “joined” but not yet feel-live.

## Settled (2026-10-20)

| # | Decision |
|---|----------|
| Q1 | Auto Mode 2 when **`br-bhvr` down** (Q11 C) |
| Q2′ | Litmus **D**: leg **A** SSH annex-B→remux→MediaMTX→**WHEP** vs leg **B** SSH MPEG-TS→**mpegts.js**; phone stopwatch |
| Q3 / Q12 | Science modal default **Lite@10** on Mode 2; Standard allowed with confirm |
| Q4 | Pass bar: feel **≲1 s** glass-to-glass (presented 3–5 fps OK) |
| Q5 | One encode; decimate for live/thumbs |
| Q6 | `buffer_count` Mode1=**6** / Mode2=**2** (auto with mode) |
| Q7 / Q9 | Auto-live **all** tiles (parity with wired); ≤1 s only on hottest — hottest UX **deferred** (Q13 C) |
| Q8 | Badge: `Mode 2 · WLAN` + backhaul/play-out nouns |
| Q13 | Hottest-tile policy after litmus winner |

### Nouns (layers)

| Layer | Means |
|-------|--------|
| Encode | Cam `rpicam-vid` (Lite/Standard, soft fps, buffer_count) |
| Backhaul | Cam → NVR (SSH annex-B, SSH MPEG-TS, USB UDP, …) |
| Play-out | NVR → browser (WHEP/WebRTC, HTTP mpegts.js) |

WHEP is play-out, not a substitute for backhaul. `buffer_count` is mostly encode achieve, not glass-to-glass latency.

## Litmus plan

1. Pick WLAN cam with working SSH (prefer cam2).
2. Mode2 knobs for run: `nvr_host=10.248.238.22`, `buffer_count=2`, idle Lite@10.
3. **Leg A** (~10 s): O1a WHEP — operator clap/LED + stopwatch; note badge fps + feel.
4. **Leg B** (~10 s): `transport: mpegts` — same.
5. Winner → Mode 2 default; then implement auto `br-bhvr` switch + badge.

## Comments

### Progress 2026-10-20

Grill locked; running A/B litmus setup on NVR.

**Leg A (WHEP):** 1-cam feel **≲1 s** (pass); ×N uneven (same as wired).

**Leg B (mpegts) first try:** black / 0 fps — cam `ffmpeg` not on PATH for non-interactive SSH (`~/bin/ffmpeg` exists). Fixed `cam_live_ssh_mpegts_remote` to prefer `~/bin/ffmpeg`. After cam clear, API pull **~620 KB / 12 s**. Operator re-stopwatch pending.

### Auto litmus (objective) — 2026-10-20

Script: `deploy/bhvr-nvr/scripts/_litmus_mode2_ab_auto.sh` (NVR).

- Flips A↔B, all online WLAN cams, CSV under `/tmp/mode2_ab_<stamp>.csv`.
- Metrics: `start_ms`, `ttff_ms` (A = RTSP ready; B = first ≥188 B HTTP MPEG-TS), `wall_fps` (ffmpeg `-c copy` / `SAMPLE_S`).
- Not glass-to-glass — clap/LED stopwatch still human.
- Manual arm-only helper remains `_litmus_mode2_leg.sh`.

**Run `20261020T225603Z`** (`SAMPLE_S=12`, `buffer_count=3`, idle Lite@10):

| Leg | ok | wall_fps min/med/max | ttff_ms min/med/max |
|-----|----|----------------------|---------------------|
| A (WHEP/RTSP) | 3/4 (cam0 not ready) | 9.33 / 12.25 / 15.50 | 505 / 1560 / 16420 |
| B (SSH mpegts) | 4/4 | 10.67 / 10.75 / 11.17 | 6870 / 11503 / 11631 |

ttff definitions differ (A ≠ cold start; B includes SSH encode start) — compare `wall_fps` spread for ×N smoothness; glass latency still stopwatch.

### Player-knob litmus (mse buffer chase) — 2026-10-21

Goal: claw glass lag on Leg B without changing cam ffmpeg.

- URL knobs: `/?chase=0|1&stash=32|64|128&paint=1` (honesty badge shows chase/stash; tile shows `buf Xs`).
- Client POSTs `/api/diag/live-player` (`buffered_s`, `stream_fps`).
- Script: `deploy/bhvr-nvr/scripts/_litmus_mode2_mpegts_player_knobs.sh` — encode baseline (LEGS=B) then waits per rung while operator hard-refreshes URLs; CSV `buffered_s_*` + optional clap note.
- Deploy helper: `_deploy_player_knobs.sh`.

### Unified science MPEG-TS (2026-10-21)

Science wire = idle shape: cam `rpicam | ffmpeg -c copy -f mpegts` + `--save-pts`.
NVR writes `*_video.ts` and **byte-tees** the same stream to live (no NVR annex-B remux).
Deploy: `_deploy_ts_science.sh`.
