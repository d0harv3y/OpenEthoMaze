# Multi-host / multi-platform DAQ grill (peek)

Do not contradict without a new grill round.

- **Status:** Rounds 1–2 confirmed. Contract + rename shipped. Win11+UVC spike measured 2026-11-03; **LIVE v1 mpegts tee** wired 2026-11-04. **Accepted:** **3-up YUYV per USB uplink**; 4-up on one hub/chain is out of product promise for these sticks.
- **Jargon:** **spike** = time-boxed throwaway-tolerant experiment that proves one risk (code may live under `moseq-mountain/` or a branch; not “the product is done”). Not an anchor commit by itself.
- **Related deferred:** [EMBEDDED_GRILL.md](EMBEDDED_GRILL.md) (Pi glass); [H5_VIEWER_GRILL.md](H5_VIEWER_GRILL.md) (export/backup); USB-UVC (merged into this grill’s cell A); SETTINGS LAN bind / auth (never grilled).
- **Operator lean:** one `bhvr-kiosk` + adapters; rename Pi trees now; then Win11+UVC spike; browser UI on Win (no embed); no Docker for spikes.

## Backlog map (so we don’t lose the thread)

| Item | Status | Notes |
| --- | --- | --- |
| LIVE/REC protocol | Shipped | [LIVE_REC_PROTOCOL_GRILL.md](LIVE_REC_PROTOCOL_GRILL.md) |
| Session / kiosk settings | Shipped | [SETTINGS_GRILL.md](SETTINGS_GRILL.md) |
| Sidecar → H5 | Shipped | |
| In-kiosk H5 viewer MVP | Shipped | Pack now; browse/play |
| H5 export → MP4 + metadata table + network backup on `/h5` | **Parked** | H5 viewer future |
| Embedded Chromium on Pi | **Deferred** Round 1 | Not for Win11 glass |
| USB-UVC as cam source | **Wired (LIVE v1)** | `capture_backend: local_uvc`; soft ≤4 bind; REC→H5; idle+REC mpegts.js tee (USB often refuses 4-up) |
| Bind kiosk on LAN + auth | Not started | Needed if Win11/laptop opens `:8080` without SSH tunnel |
| Flat `~/bhvr-*` on NVR | Mostly done | Install scripts / docs still mention `deploy/` |
| Maze `trials.h5` bridge | Out of scope | |

## Product split (proposed vocabulary)

```
bhvr-kiosk          → multi-platform CONTROLLER (UI + session + H5 pack + orchestration)
                      adapters: who captures, how LIVE is published

bhvr-cam-pi0w       ← rename today’s deploy/bhvr-cam-pi0w (appliance image / firstboot / rpicam)
bhvr-nvr-pi4b       ← rename today’s deploy/bhvr-nvr-pi4b (mosquitto, mediamtx, SSD, labwc helpers)
bhvr-nvr-win11      → NEW host appliance (service install, dshow/MF, paths, no labwc embed)
```

**Keep as one product (`bhvr-kiosk`):** FastAPI console, operator state, session folders, H5 schema/pack/viewer, pack jobs, science knobs UI, journal — anything that talks **archive + operator intent**.

**Split as host/cam appliances (do not pretend these are portable):**
- Pi0W: rpicam, gadget, MQTT announce, slim disk
- Pi4 NVR: MediaMTX, mosquitto, beacon, SSD automount, optional embed
- Win11 NVR: Windows service, USB enum, GPU/QSV encode, Defender/firewall, no MQTT-required if cams are local

You are right: **most of `bhvr-cam` / `bhvr-nvr` does not reuse on Win11.** Rename-for-clarity is honest. Reuse is the **kiosk + H5 contract**, not the shell scripts.

## Where the code actually splits

```
                    ┌─────────────────────────┐
                    │      bhvr-kiosk          │
                    │  UI · session · H5 pack  │
                    └───────────┬─────────────┘
                                │ CapturePort / LivePort (interface)
           ┌────────────────────┼────────────────────┐
           ▼                    ▼                    ▼
   PiCamSSHAdapter      LocalUvcAdapter       (future…)
   (Linux or Win11      (Win11 dshow /        RTSP? etc.
    host talking to      Linux v4l2)
    bhvr-cam-pi0w)
```

Cross-matrix you named:

| Host \ Cam | Pi0W (HW H.264 SSH) | Local USB YUYV |
| --- | --- | --- |
| **Pi4 NVR** | **Today** | New Linux UVC adapter |
| **Win11 NVR** | New: Win OpenSSH client + same remote recipe | New: dshow/MF + encode |

So yes: **Pi-from-Win11** and **UVC-on-Linux** are two adapter cells — not “reproduce the whole NVR twice,” but also not free.

## Docker / Frigate — uniforms vs the mess

| Claim | Reality |
| --- | --- |
| Docker = write once run anywhere | Helps **ship ffmpeg/mediamtx/deps** with one image. Does **not** erase USB passthrough, Windows services, GPU encode drivers, or “SSH to a Pi on the LAN.” |
| Frigate | Excellent **security-cam NVR** (detect, retain, MQTT). Different product contract (clips/events, not our session/H5/subject metadata). Using Frigate = adopt their model or glue painfully — not a free portability layer for bhvr. |
| Fancy cross-platform | The durable split is **interfaces + archive schema**. Containers are packaging. Electron/Tauri would only wrap the UI; capture still needs native adapters. |

So: Docker can **uniform the controller runtime** on Linux/Win (WSL2 caveats for USB). It is **the same mess with better uniforms** if you expect it to replace `CapturePort` design.

## Clash with deferred grills

| Deferred | Clash / interaction |
| --- | --- |
| **Embedded (Pi)** | Orthogonal if Win11 is **browser/laptop only** (your lean). Don’t design embed for Win. Pi embed stays Pi4-only. |
| **USB-UVC** | **Same capture-plane work** as Win11 local cams. Should be one “local UVC adapter” story, not two grills that diverge. |
| **H5 export/backup** | Host-agnostic once files exist — **less** clash; do after multi-host or in parallel on Pi. |
| **LAN bind + auth** | **Hard clash** if Win11 kiosk is used without SSH tunnel — unauthenticated `:8080` on a lab PC is worse than localhost-on-Pi. Grill before exposing. |

## Round 1 — frontier (elaborated)

### Q1 — Controller product shape

**What this decides:** Is `bhvr-kiosk` the long-lived product name for “operator console + session + H5,” or do Windows and Pi get separate apps that only agree on file format?

| | Meaning | Buys you | Costs you |
| --- | --- | --- | --- |
| **A** | **One `bhvr-kiosk`** package. Host trees (`*-pi4b`, `*-win11`) only *install and run* it. Capture/LIVE behind adapters (`PiCamSSH`, `LocalUvc`, …). | One UI, one H5 packer, one `/h5`, one settings story. Pi and Win diverge only where hardware forces it. | Must design interfaces *before* the second host is pleasant. Risk of “abstraction theater” if Win never ships. |
| **B** | Fork **`bhvr-kiosk-win`** (or similar). Share a thin H5 library; UI/session code may copy-paste or drift. | Fast Win spike without touching Pi paths. No fear of breaking cage-night. | Two consoles forever. Every grill (export, pack-now, LIVE UX) gets done twice or silently diverges. |
| **C** | Kiosk stays **Pi-only**. Win11 is a **headless/minimal DAQ** that writes the same H5 (CLI or tiny UI). Operators use Pi glass or SSH-tunnel to Pi for “real” kiosk. | Clearest boundary; Pi fleet undisturbed. | Win never gets the console you already invested in; “same product” is only the archive. |

**How to think about it:** If the value is “same buttons, same H5, different wires,” pick **A**. If the value is “get USB cams recording this month on the lab PC,” **B** or **C** is honest short-term — but **B** is the worst long-term (two UIs). **C** is the honest “Win is a writer, Pi is the product.”

**Recommendation:** **A** — with a rule: no adapter interface until Q3 picks a first cell (avoid boiling the ocean).

---

### Q2 — Rename timing (`bhvr-cam` → `bhvr-cam-pi0w`, etc.)

**What this decides:** When do paths/docs stop lying that “cam” and “nvr” are generic?

| | Meaning | Buys you | Costs you |
| --- | --- | --- | --- |
| **A** | **Rename now** (git mv under `deploy/`, fix install scripts, NVR `~/bhvr-cam` → `~/bhvr-cam-pi0w` or keep runtime dirs and only rename *repo* trees). | Mental model matches reality before Win11 exists. New contributors don’t assume Win fits in `bhvr-nvr`. | Churn: docs, scp habits, any hardcoded `~/bhvr-cam` / `deploy/bhvr-nvr-pi4b` (we already moved off `~/deploy/`). Runtime rename on the live NVR is optional and riskier than repo rename. |
| **B** | Rename **when the first Win11 spike** lands (same PR as `bhvr-nvr-win11` skeleton). | One migration wave; no rename if multi-host dies. | Until then, names keep implying portability that isn’t there. |
| **C** | **Never rename**; README says “pi0w/pi4b only.” | Zero path churn. | Permanent confusion; `bhvr-nvr-win11` beside `bhvr-nvr` looks like a fork of a generic thing. |

**Subtlety:** Repo rename ≠ NVR home rename. You can `deploy/bhvr-cam-pi0w` in git while the Pi still has `~/bhvr-cam` until a soft-push install path updates. Grill should eventually say which layer renames.

**Recommendation:** **A** for *repo/docs*; defer *live NVR directory* rename until soft-push/install scripts are touched (or keep runtime names stable forever and only rename deploy trees).

---

### Q3 — First new cell to build

**What this decides:** Which box in the host×cam matrix we actually implement first — that choice teaches different lessons.

```
              Pi0W (SSH HW H.264)     Local USB YUYV
Pi4 NVR       [ TODAY ]              [ C ]
Win11 NVR     [ B ]                  [ A ]
```

| | Cell | Proves | Does *not* prove | Fits your desk USB stick? |
| --- | --- | --- | --- | --- |
| **A** | Win11 + local UVC | Fat PC can capture→encode→same H5; Win service/paths; dshow pain | Still need SSH-to-Pi for cage fleet; Linux UVC separate | **Yes** — direct |
| **B** | Win11 + Pi0W cams | Controller runs on Win; OpenSSH + annex-B recipe; roster/MQTT-from-Win | USB farm; encode-on-PC | No (needs fleet online) |
| **C** | Pi4 + local UVC | v4l2 on Linux NVR; USB on appliance you already own | Win packaging; “Windows as NVR” | Yes if you plug stick into NVR |
| **D** | Spec only | `CapturePort` / LIVE port / H5 invariants written down | Anything works in hardware | N/A |

**Motivation test:**
- “I have a YUYV stick and a lab PC” → **A** (or **C** if the PC isn’t the long-term host).
- “I want the cage Pi cams driven from a Windows box in the lab” → **B**.
- “I’m scared of thrashing Pi production” → **D** first, then a spike on a non-production machine.

**Recommendation:** **D** for a short written contract (1–2 pages in this grill or `docs/`), then **A** or **B** as a spike — don’t do A and B in parallel.

---

### Q4 — Win11 UI posture

**What this decides:** Is the Windows machine a **DAQ host you browse to**, or a **touch kiosk appliance**?

| | Meaning | Buys you | Costs you |
| --- | --- | --- | --- |
| **A** | Operator opens Edge/Chrome → `http://127.0.0.1:8080` (or later LAN+auth). No fullscreen embed, no autostart browser. | Matches your lean; avoids EMBEDDED_GRILL on Windows; SSH tunnel from another laptop still works the same. | Someone must know the URL; no “walk up and it fills the monitor” unless they leave a browser open. |
| **B** | Autostart Edge/Chromium `--kiosk` on the Win box (embedded). | Cage-night energy on a big monitor. | Second embed product; Windows update/kiosk escape/Defender; clashes with deferred Pi-only embed focus. |

**Interaction with security:** **A** + localhost-only is fine. **A** + LAN bind without auth is dangerous on a lab PC. **B** doesn’t remove the need for auth if the machine is shared.

**Recommendation:** **A**.

---

### Q5 — Docker’s job (if any)

**What this decides:** Is Docker part of the *product*, or a packaging footnote?

| | Meaning | Buys you | Costs you |
| --- | --- | --- | --- |
| **A** | **No Docker** for first spikes. Native Python venv + system/winget ffmpeg on Win; existing venv on Pi. | Fastest learning; USB/dshow/SSH behave normally. | Dep install docs per OS. |
| **B** | Docker **only** for sidecar deps (e.g. MediaMTX, maybe ffmpeg) on Linux; UI and capture stay native. | Uniform “how we run mediamtx” on Pi/x86 Linux. | Two moving parts; Win still native for capture. |
| **C** | “Whole stack in Docker” including capture. | Pretty Compose file on Linux. | Win11 USB passthrough + GPU encode + GUI is a famous tar pit; debug hell; not how Frigate feels magic either — they still fight devices. |

**Frigate analogy:** Frigate’s win is a **opinionated pipeline + UI**, not “Docker erased cameras.” Copying Frigate’s *idea* (clear roles) helps; copying Frigate’s *stack* replaces bhvr.

**Recommendation:** **A** until a second Linux host makes MediaMTX install annoying — then consider **B**.

---

## Confirmed (Rounds 1–2)

| # | Decision | Choice |
| --- | --- | --- |
| Q1 | Controller product | **A** — one `bhvr-kiosk` + capture/LIVE adapters |
| Q2 | Rename timing | **A** — rename repo/docs now (`bhvr-cam-pi0w`, `bhvr-nvr-pi4b`); go gentle on live NVR home dirs |
| Q3 | First cell | **D then A** — contract, then Win11 + local USB YUYV spike |
| Q4 | Win11 UI | **A** — browser to localhost; no embed |
| Q5 | Docker | **A** — none for spikes |
| Q6 | CapturePort output | **A** — MPEG-TS (+ optional pts); adapter owns encode |
| Q7 | LIVE on first spike | **C→v1 done** — crude stills retired; idle+REC mpegts.js tee on local_uvc |
| Q8 | USB cam identity | **A** — stable USB id; litmus ran → **accept 3-up / uplink** (4× FAIL) |
| Q9 | Contract deliverable | **C** — doc + Protocol + fake adapter tests |
| Q10 | Rename with contract | **A** — git mv + `bhvr-nvr-win11` stub when go |

### Docker primer (why Q5=A is not anti-Docker forever)

Docker is **not** a multi-platform Python env and **not** a replacement for `uv`/`pip`/`apt`/`winget` inside your app.

Rough analogy:

| Thing | What it is |
| --- | --- |
| **venv / uv** | Isolated *Python packages* on the host OS. |
| **apt / winget** | Install *system* programs (ffmpeg, chromium) on the host. |
| **Docker image** | A **mini Linux filesystem** with programs already installed, started as an isolated process (container). You run *someone else’s (or your) pre-baked machine recipe*. |

It **bundles dependencies** into an image (ffmpeg, mediamtx, libraries) so “docker run …” looks the same on two Linux boxes. It **adds** a dependency: Docker Engine (and on Windows, usually WSL2 + Docker Desktop). It does **not** magically make USB cameras or SSH-to-Pi portable — you still pass devices/network in, and that is the hard part.

For bhvr spikes: native venv + installed ffmpeg teaches capture truth faster. Revisit Docker later only if repeating MediaMTX/ffmpeg install across Linux hosts is the pain.

---

## Round 2 — CapturePort / H5 contract (Q3=D)

Before the Win11+UVC spike, lock what every adapter must honor so Pi-today and Win-tomorrow write the **same** science archive.

### Q6 — Minimum CapturePort outputs

What must an adapter hand the controller during REC?

| | |
| --- | --- |
| **A** | **MPEG-TS bytes + optional pts** (same as today after NVR remux). Adapter owns encode/remux. |
| **B** | **Annex-B H.264 + pts**; controller always remuxes to TS (one remux path). |
| **C** | **Raw frames** (YUYV/RGB); controller owns all encode (heavy, one place). |

**Recommendation:** **A** for multi-host — Pi adapter already ends at TS; UVC adapter encodes to TS on the PC. Avoid **C** (controller becomes an encoder farm).

### Q7 — LIVE vs REC coupling

| | |
| --- | --- |
| **A** | Same as Pi grill today: one encode; LIVE is a tee/view of science bytes (or stop idle publisher while REC). |
| **B** | Allow dual path on fat Win host (cheap preview encode + science encode) — only if spike proves need. |
| **C** | REC-only on Win spike; LIVE “tap tile” can be “open VLC” / still JPEG for v0. |

**LIVE crude (Q7=C) means:** first Win+UVC milestone does **not** need tile WHEP/mpegts.js parity with the Pi NVR. REC must write proper MPEG-TS into H5. For “is the cam working?” allow something cheap: still JPEG refresh, open the device in a desktop viewer, or a one-cam local ffmpeg preview — enough to aim the stick, not cage-night LIVE.

**Upgrade path crude → LIVE parity (same CapturePort, add a LivePort):**

1. **Spike v0 (crude):** adapter writes science MPEG-TS to disk/H5; preview is out-of-band or stills. Proves encode+pack+hub bandwidth.
2. **LIVE v1 (local tee):** while REC (or idle), adapter exposes the **same MPEG-TS** (or a ring buffer) on `http://127.0.0.1:…/camX.ts`; console tiles use existing **mpegts.js** (already in kiosk) — parity with Pi “mpegts transport,” no MediaMTX required on Win.
3. **LIVE v2 (optional):** if idle needs a lighter stream than science, add a second encode — only if v1 is too heavy. That is Q7=B territory; not in the contract until measured.
4. **Pi parity checklist:** tile start/stop, fail/retry badges, multi-cam grid — UI already exists; Win adapter just has to feed URLs/bytes. WHEP/MediaMTX on Win is **optional**, not required for “feels like kiosk LIVE.”

So crude is not a dead end: it skips *publishing* into the console until REC→H5 is real. The upgrade is “point mpegts.js at the adapter’s TS,” not a rewrite.

**Recommendation:** **C** for the *first* Win+UVC spike, with the upgrade ladder above written into the contract. Don’t invent dual-encode until v1 is too slow.

### Q8 — Cam identity on local USB

Operator has **multiple** desk USB cams; spike must stress **4 streams on one hub** (bandwidth / hub chipset litmus — often the real failure mode for YUYV).

| | |
| --- | --- |
| **A** | Stable ID from USB serial / VID:PID+port path when available; fallback `uvc-0`… |
| **B** | Operator-assigned names only (sticky config map device → `cam_id`). |
| **C** | DirectShow friendly name as id (fragile across unplug). |

**Recommendation (revised):** **A** — needed once ≥2 identical sticks exist; map stable key → display `cam_id` in config if you want pretty names.

**Confirmed lean:** **A** (2026-11-03). Hub litmus ran.

**Litmus + decision (2026-11-03):** 4× `vid_1871` YUYV listed + solo/H5 OK; **3× concurrent PASS**, **4× FAIL** (isochronous reservation / one uplink — not MiB/s). **Accept 3-up per USB uplink** for Win11+UVC with these sticks. Revisit only with split roots, MJPEG/H.264 cams, or non-dshow. Details: `deploy/bhvr-nvr-win11/README.md`.

### Q9 — Scope of the written contract (D deliverable)

| | |
| --- | --- |
| **A** | One short doc in `deploy/bhvr-kiosk/docs/capture_port.md` (or section in this grill): H5 layout invariants + CapturePort methods + non-goals. |
| **B** | Full typed Protocol in code + tests with a fake adapter (no hardware). |
| **C** | Both: doc + skeletal Protocol + fake adapter tests, still no UVC yet. |

**Recommendation:** **C** — executable spec matches your V&V habits; still “D” (no Win capture yet).

### Q10 — Repo rename in the same breath as the contract?

| | |
| --- | --- |
| **A** | Yes — git mv `bhvr-cam`→`bhvr-cam-pi0w`, `bhvr-nvr`→`bhvr-nvr-pi4b` + stub `bhvr-nvr-win11/README.md` when Round 2 closes / you say go. |
| **B** | Contract first; rename in a dedicated pass after. |
| **C** | Rename only after Win+UVC spike works. |

**Recommendation:** **A** — Q2=A already; doing it with the contract avoids two “big layout” moments. Live NVR `~/bhvr-cam` can lag.
