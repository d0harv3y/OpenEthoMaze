# Grill: kiosk encode presets (honest science ask + live display)

Type: grilling  
Status: resolved (v0 prototype scope locked 2026-10-19)  
Blocked by: 10  
Unblocks: [13-task-science-ask-prototype.md](13-task-science-ask-prototype.md)

## Question

Replace the dishonest `sensor_mode` context menu with an honest **science ask** (what is encoded) and a separate **live display** policy (what the kiosk shows). Stress/ladder numbers are in; presets can ship.

## Nouns

| Say | Means |
|-----|--------|
| **Science ask / encode** | What `rpicam-vid` writes (mode × size × soft fps × bitrate × buffer_count) — **cam-side**, fixed at encode start. |
| **Live display** | What the tile paints (shrink-to-fit, decimation) — **kiosk/NVR-side**; may change without restarting science. |
| **Soft / presented / achieved fps** | ask / badge / pts. |
| **Standard / Lite** | Operator labels for `1296×972` (2×2 bin) / `640×480` (heavy bin). Both **4:3**, no 16:9 crop. |

## Settled (2026-10-19)

| # | Decision |
|---|----------|
| Q1 | Kill operator `sensor_mode` menu/API; bake mode under size ask |
| Q2 | Science ask **session-global** v1; context menu leftovers = live on/off + metadata |
| Q3 | Session **New** modal authoritative; Settings lab-defaults deferred |
| Q4→Q12′ | **No focus** for now. Display **decimation slider** (default keep 1/10). `buffer_count` fixed **6** in v0 (slider later) |
| Q5 | HTU21D **out of trunk** — thin follow-on |
| Q6 | **4:3 only.** Drop 1080 crop. Standard=`1296:972`+1296×972; Lite=`640:480`+640×480. No crop/stretch (pillarbox OK) |
| Q7 | Touch chips: size × fps (not nested menus) |
| Q8 | File-size hard-stop **deferred** with Settings; soft ETA later |
| Q9 | Decimation knob yes; buffer_count slider later |
| Q10 | Honesty badge **always**; Diagnostics strip later |
| Q11 | **C** — Standard/Lite labels; fps 30 / **20\*** / 15 / 10 |
| Q12′ | B + drop focus; thumbs = received stream, shrink-to-fit, display 1/N |
| Q13 | Settings knob inventory **deferred** — prototype first |
| Q14 | **Hard A** — mid-record science ask **read-only** |
| Q15 | **A** — v0: kill sensor menu; modal chips; idle Lite@10; decimate 1/10 + slider; buf=6; honesty badge |
| Q16 | **B** — idle encode always **Lite@10**; Start promotes to session ask |

### Cam vs kiosk ownership

**Cam (must be in remote cmdline before first NAL):** mode, width/height, soft fps, bitrate, intra, buffer_count, flush/inline/codec.

**Kiosk/NVR only:** display decimation, shrink-to-fit, honesty/diagnostics badges, session modal, MediaMTX ports, disk ETA.

### Side notes (facts, not open decisions)

- OV5647 has no native 1280×720 mode; mid 16:9 was always a crop or a scale from another mode.
- Pi “4K capable” ≠ 4× H.264 soft decode; pixel-count analogy undersells multi-pipeline cost.
- Older Mode‑1 pts dig (buf=2): 2×2→720p ~17 fps; heavy 640×480 ~23; 1080 crop ~15. Science path with buf≥6 hits ~29 @ 1080 crop — expect Standard/Lite soft 20–30 reachable; re-litmus native 4:3 @ buf=6 when convenient.

## Still deferred

- Settings Apply / lab-default persistence
- File-size hard stop
- `buffer_count` slider
- NVR Stage‑B decode-less (true skip before soft decode)
- HTU21D MQTT/API + kiosk readout
- Per-cam science overrides
- Mode 2 RTSP product soft-cap K
