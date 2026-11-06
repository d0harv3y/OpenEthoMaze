# LIVE / REC lifecycle protocol grill

Do not contradict without a new grill round.

- **Status:** Round B **confirmed** + UI shipped 2026-10-30. Round A **confirmed** + **implemented** 2026-10-30 (no reload; parallel=2; data-driven ready; Stop S2+ pack banner + Start gate).
- **Hotfix 2026-10-30:** 0-byte `.ts` + settle hang — race: UI `clearFocus`→`/api/preview/stop` freed/pkill'd science before `.active_session.json` existed. Fix: in-memory `_science_guard` before idle stop; await preview/stop before Start; refuse session if no capture; one header REC banner (tile REC chrome retired).
- **Ops note:** `systemctl restart` can leave an orphan uvicorn on `:8080` while the unit crash-loops (`address already in use`). Kill the holder then start — otherwise disk deploys never load.
- **Hotfix 2026-10-30b:** REC header timer starts only after SSD bytes (`REC arming…` until then). Stop pack recovers subject from active meta / `.ts` stem / existing `*__{cam}.h5` shell (no more `unknown__` when only cam0 was armed).
- **Hotfix 2026-10-30c:** Start 503 was dumping ffmpeg spam; cam remux used `-fflags nobuffer` → probesize 0 → `Output file does not contain any stream` / 0-byte `.ts`. Fix: `-probesize 2M -analyzeduration 2M`, short modal error.
- **Hotfix 2026-10-30d:** `exited rc=… (SIGPIPE)` = cam ffmpeg died (malformed H264 after reclaim), rpicam wrote into closed pipe. Science now matches idle: annex-B SSH + **NVR** remux. LIVE autostart gets one silent retry before `fail (tap LIVE)`.
- **Hotfix 2026-10-30e:** Per-cam tile REC tag shows SSD KB/rate; header timer is elapsed-only after first bytes. **Operator event journal** (interaction + consequence breadcrumbs) at `data_root/.kiosk_journals/` — page-session = browser load, max 24 sessions / ~400 KiB then soft reload. Science Start retries once on reclaim race.
- **Hotfix 2026-10-30f:** Start modal busy-state (disable Start/Cancel, progress copy, no double-submit). Header Start no longer pre-checks **all** cams — only the tile that opened the modal (or none). Failed promote restores LIVE only on cams that were torn down.

## Future scope (not started)

### Sidecar fold-into-H5 (shipped)
On each part pack (roll + Stop): delete loose after verify.
| Loose | H5 |
| --- | --- |
| `*.ts` / `*.pts` | `video/mpegts_NNN` / `video/pts_NNN` |
| `*_capture.log` / `*_remux.log` | `logs/capture_NNN` / `logs/remux_NNN` (skip+delete if empty; remux = NVR ffmpeg stderr) |
| `*_fps.json` | attr on `mpegts_NNN` (`fps_file_json`) |
| `{subj}__{cam}_env.jsonl` | `logs/env_jsonl` (Stop only) |
| `.{cam}_pts_full.pts` | `logs/pts_full` (Stop only) |
| `stop_log.json` | root attr `stop_log_json` (Stop; **loose kept**) |
`.capture_pids.json` stays session-local (not folded).

### In-kiosk H5 viewer (myhdf5-class)
Moved to dedicated grill: [H5_VIEWER_GRILL.md](H5_VIEWER_GRILL.md) (Round 1 open). Do not merge into this lifecycle doc.

## Scope in

- Per-cam / session **visible phases** and who owns each transition (browser vs NVR).
- **One retry policy** per phase (who retries, max attempts, backoff).
- **Anti-thrash defaults** owned here (grace, dead-fps, online latch, stagger) — not only as comments in `app/templates/index.html`.
- After B ships: Round A — no full `location.reload()` on Start/Stop; parallel cam bring-up; promote idle→science without blacking the whole grid.

## Scope out

- Dual encode for cheap preview.
- Science size / fps / chunk / recording tag / H5 defaults → SETTINGS_GRILL.
- USB push / Wi‑Fi / backup / data_root → SETTINGS_GRILL Kiosk settings.
- Maze `trials.h5` bridge.

---

## Current behavior snapshot (as of 2026-10-30)

Two pipelines with a hard cut: idle **WHEP** (MediaMTX) vs science **SSH MPEG-TS** to SSD. REC tears idle LIVE down, blocks on per-cam start, then full page reload; after reload, REC cams use mpegts tee and non-REC cams WHEP again.

### Anti-thrash (browser)

| Knob | Value | Role |
|------|------:|------|
| `LIVE_DEAD_FPS` | 0.5 | Dead only if essentially frozen |
| `LIVE_STALL_S` | 30 s | Must stay dead this long before stall note |
| `LIVE_WATCH_GRACE_MS` | 60 s | No stall judgment after start / re-track |
| `LIVE_RETRY_BASE` / `MAX` | 15 s → 120 s | Backoff map exists; stall path does **not** auto-restart |
| Online latch | 4 misses (~20 s @ 5 s poll) | MQTT blips before `clearFocus` |
| Link-flip debounce | 5 s | USB↔WiFi may reattach once |
| Auto-start stagger | 1 s + 3 s × i | Avoid 4× `whep/start` storms |
| Empty-grid reload | off | Was reload→fail→reload thrash |

Stall = **badge only** (“stall (tap to retry)”). Preview fail does **not** call `/api/preview/stop` or auto-retry.

### LIVE idle start

Page load → roster poll 5 s → `autoStartOnlineLives` @ 400 ms → staggered `setFocus` → `POST .../whep/start` (SSH settle USB 2.5 s / WiFi 4 s, one retry) → WHEP reader (20 s track timeout) → fps counter + 60 s grace.

Encode ask = Session settings size×fps. Session Apply → `stop_all_idle_previews` → 1.5 s → `autoStartOnlineLives`.

### REC start / stop

Start modal → `clearFocus()` → `POST /api/session/start` → `stop_all_idle_previews` → per cam **serial** science pipe + **`sleep(2)`** → chunk roller → `.active_session.json` → **`location.reload()`**. Stop: clearFocus → pack/stop → reload.

### Why it feels rough (irritating, not blocking)

1. Hard cut idle↔science + full reload.
2. Serial `sleep(2)` per cam on Start.
3. Anti-thrash mostly “don’t auto-heal.”
4. Blunt stagger; first tile live while others black.
5. No shared phase strip (connecting / settle / live / promoting / recording).

---

## Round B — visible state machine (confirmed 2026-10-30)

### B1. Phase list

| Phase | Operator-visible? | Owner | Meaning |
|-------|-------------------|-------|---------|
| `offline` | yes (status) | roster | MQTT stale / not online |
| `connecting` | yes (fps tag) | browser | `setFocus` / whep/start in flight |
| `settle` | yes (fps tag) | NVR+browser | Publisher up; waiting track / first frames (within grace) |
| `live` | yes | browser | Decode fps ≥ dead floor; normal LIVE |
| `stall` | yes | browser | Past grace; near-zero fps; **no** auto teardown |
| `fail` | yes | browser | Start/track failed; tap to retry |
| `promoting` | yes (tile + optional header) | NVR | Science pipe starting for this cam (Round A makes this real; Round B may show only after Start returns until A) |
| `recording` | yes (rec tag + write stats) | NVR+browser | Capture writing; LIVE = tee if focused |
| `stopping` | yes | NVR | Stop / pack in flight |

Log-only (not a tile phase): SSH litmus detail, remux retry #1, pack background lines.

### B2. Retry policy

| Phase / event | Policy (proposed) |
|---------------|-------------------|
| `connecting` / whep/start 503 | No browser auto-loop. Server already one settle retry. Tap → retry. |
| `fail` | Tap only. Exponential backoff map retained for **explicit** `scheduleLiveRetry` only if we re-enable it later. |
| `stall` | Badge only; **one** optional bounded auto-retry **off** by default (keep tap). If enabled later: 1 attempt after `LIVE_STALL_S`, then tap. |
| Online→stale | After 4 latch misses: leave `live`/`stall` → tear browser session (`clearFocus`). |
| USB↔WiFi link flip | Debounced reattach (5 s): clear + `setFocus` after 600 ms. |

### B3. Stagger / bring-up

- **Cold load & Session Apply:** keep timed stagger **1 s + 3 s × i** for Round B (document only; no change required to ship B chrome).
- Round A may switch to “next cam when previous reaches `live` or timeout (e.g. 20 s)” — **not** confirmed here.

### B4. Session Apply vs cold load

- **Same phase strip** as cold load (`connecting` → `settle` → `live` / `fail`).
- Apply still stops idle publishers server-side; browser clears tiles then re-enters the same phase machine (today: 1.5 s then `autoStartOnlineLives`).

### B5. Chrome (where phases show)

- **Tile fps tag:** `connecting` / `settle` / `live` (fps text) / `stall (tap…)` / `fail` hints (keep existing hint vocabulary where possible).
- **Tile status line:** ONLINE/STALE · USB/WiFi (unchanged); while `promoting`/`recording`/`stopping`, status may stay recording-oriented.
- **Header:** REC timer + science chip only while session active — no new global phase parade in Round B.
- **Honesty banner:** unchanged (REC* disk can beat LIVE).

### B6. Anti-thrash defaults (grill-owned numbers)

Round B **adopts current values** as grill defaults (change only with a new round):

- `LIVE_DEAD_FPS` = 0.5  
- `LIVE_STALL_S` = 30  
- `LIVE_WATCH_GRACE_MS` = 60000  
- Online latch misses = 4  
- Link-flip debounce = 5 s  
- Auto-start: delay0 = 1000 ms, stride = 3000 ms  
- WHEP track timeout = 20 s  
- Server settle budget: USB 2.5 s / WiFi 4 s; one publish retry  

### Round B confirm checklist

- [x] B1 phases (+ visible vs log-only)
- [x] B2 retry (stall stays tap-only)
- [x] B3 stagger kept for B
- [x] B4 Apply shares phase strip
- [x] B5 chrome placement
- [x] B6 numbers locked

Round B UI work allowed (phase strip / fps-tag vocabulary only). Still no Round A reload removal until A is confirmed.

---

## Round A — promote without reload (confirmed 2026-10-30)

Round B UI is in. **A implementation allowed.**

### Goals

1. Start/Stop keep SPA state — **no** `location.reload()`.
2. Kill WHEP / idle encode **only** for cams entering the science session (others keep idle LIVE).
3. Parallel science SSH starts with **max concurrency 2**.
4. Data-driven ready check instead of fixed `sleep(2)`.
5. REC cams flip browser transport to mpegts tee without full reload; non-REC tiles stay on idle WHEP.
6. Tile phases: `promoting` → `recording` → `stopping` → idle LIVE restore (`connecting`…`live`).
7. Idle LIVE stagger stays Round B timed (1 s + 3 s × i); science Start uses parallel-2 pool (not next-cam-on-live).

### A answers locked

| Q | Answer |
|---|--------|
| Max parallel science SSH starts | **2** |
| Ready check | **Data-driven** (not fixed 2 s timer) |
| Stop policy | **S2+** — background pack, early LIVE restore, pack-status on recording banner, **gate Start while `pack_pending`** |

**Data-driven ready:** after SSH pipe opens, poll until either (a) capture proc still alive **and** loose `.ts` has grown by ≥ N bytes (e.g. 188×50) within budget T (e.g. 5 s), or (b) proc exited → per-cam FAIL. No global barrier on other cams in the pool.

### Stop policy (confirmed) — S2+

```
operator hits Stop
  → tiles: stopping (brief)
  → POST /session/stop: kill pipes + pull pts + clear active session FAST
     queue final H5 pack(s) background (same family as chunk-roll _pack_part_async)
  → response: session cleared; pack_pending=true (or job list)
  → restore idle LIVE immediately (autoStartOnlineLives)
  → header “recording banner” becomes pack status while pending
     (e.g. PACK 2/4… → PACK OK / PACK fail — keep loose TS on fail)
  → poll /api/…/pack-status until idle
  → Start disabled while pack_pending (global queue non-empty)
```

Rejected for A v1: **S1** (block Stop until pack). Optional later: “Wait for archive” checkbox → S1 behavior.

S1/S2/S3 writeup kept below as design history only.

<details>
<summary>Design history — S1 / S2 / S3 options</summary>

**S1** — block UI until kill+pts+pack done; high certainty; long `stopping`; HTTP timeout risk.

**S2** — early LIVE + background pack; needs visible status + Start gate to be safe.

**S3** — named hybrid of S2 + Start gate + visible fail; **confirmed shape is S2+** (banner poll + Start gate), same intent as S3.

</details>

---

## Non-goals (this grill)

- Dual encode preview path.
- Rewriting kiosk copy/language beyond phase tags.
- Changing MQTT stale_after or announce protocol.
- Frigate / HA / maze pipeline integration.

---

## Code touchpoints (for implementers after confirm)

- Browser: [app/templates/index.html](app/templates/index.html) — `liveSessions`, `autoStartOnlineLives`, fps watchdog, Start/Stop reload.
- Server: [app/main.py](app/main.py) — `api_preview_whep_start`, `start_cameras`, `_begin_session`, settle budgets, `stop_all_idle_previews`.
- Cam free: [app/preview.py](app/preview.py) — `cam_free_encode_remote`.
