# NVR embedded Chromium grill

Do not contradict without a new grill round.

- **Status:** Round 1 **deferred** 2026-11-02 (operator pause — revisit later).
- **Related:** [SETTINGS_GRILL.md](SETTINGS_GRILL.md) (privileges / Wi‑Fi on glass); [LIVE_REC_PROTOCOL_GRILL.md](LIVE_REC_PROTOCOL_GRILL.md) (console behavior); [H5_VIEWER_GRILL.md](H5_VIEWER_GRILL.md) (`/h5` is a second page — same Chromium).
- **Fact — performance:** Embedded / `--kiosk` does **not** cost more than windowed Chromium. Same renderer, same LIVE decode. The NVR is **already** paying that bill (labwc + Chromium → `:8080`, often 4× LIVE). “Thermals” here means: locking the glass does not **reduce** load, and makes it harder to bail to a light desktop if the Pi is hot. Optional later: a **kiosk operator profile** (fewer auto-LIVE tiles) — orthogonal to embed chrome.

## Facts (looked up)

- Runtime today: **lightdm** → **labwc** → Chromium via `~/.config/autostart/bhvr-kiosk-chromium.desktop` (windowed-ish: `--password-store=basic`, **no** `--kiosk`).
- Unused draft unit: `bhvr-kiosk/systemd/bhvr-kiosk-browser.service` (`--kiosk`, `DISPLAY=:0`, after web).
- Web: `bhvr-kiosk-web` on `127.0.0.1:8080`.
- SETTINGS grill: embedded does not change sudoers; prefer USB/wired for NVR Wi‑Fi Apply from glass.

## Scope in (proposed)

- How Chromium is started, restarted, and locked to the console URL.
- Cold-boot ordering: graphical session ↔ uvicorn ready.
- Operator escape / laptop admin path.
- Install/refresh wiring under flat `~/bhvr-*`.

## Scope out (until later)

- Rewriting the console UI for a phone form-factor.
- Binding uvicorn on LAN by default.
- Changing LIVE encode / auto-start policy (may be a follow-on “kiosk profile” round).

---

## Round 1 — frontier

### Q1 — Lock level

How hard is the glass locked?

| | |
| --- | --- |
| **A** | **Soft kiosk:** Chromium `--kiosk` fullscreen on `:8080`; OS still reachable if someone plugs a keyboard (Alt+F4 / tty). |
| **B** | **Hard appliance:** kiosk + hide panel/cursor; no easy desktop escape without SSH or a documented gesture. |
| **C** | **Stay soft-windowed** (current): improve autostart reliability only; no `--kiosk`. |

**Recommendation:** **A** — enough for cage-night; SSH remains the real admin hatch.

### Q2 — Autostart mechanism

| | |
| --- | --- |
| **A** | Keep **labwc autostart `.desktop`** (update flags to `--kiosk`); simplest on Pi OS. |
| **B** | Enable **`bhvr-kiosk-browser.service`** (user or system) after web; drop/disable `.desktop` to avoid double Chromium. |
| **C** | Both: `.desktop` for interactive login, systemd as watchdog — only if we prove no double-start. |

**Recommendation:** **A** for MVP (matches what already works). Promote to **B** only if crash/restart needs a real unit.

### Q3 — Wait for web

Before Chromium loads the URL:

| | |
| --- | --- |
| **A** | Poll `http://127.0.0.1:8080/api/health` (or `/`) up to N seconds, then open. |
| **B** | Fixed sleep (current draft unit: 2s). |
| **C** | Chromium opens immediately; UI shows “waiting for backend…” if fetch fails (retry in page). |

**Recommendation:** **A** + short fallback sleep — avoids blank/crash-restore on cold boot.

### Q4 — Escape / admin

| | |
| --- | --- |
| **A** | Document SSH + laptop browser to `http://<nvr>:8080` only if we bind LAN; else SSH tunnel / local `:8080`. **No** on-glass exit. |
| **B** | Hidden gesture / long-press header → “Exit kiosk” (closes Chromium to labwc desktop). |
| **C** | Keyboard: Ctrl+Alt+E or similar exits kiosk. |

**Recommendation:** **A** for cage floor; **B** later if techs need glass-only recovery. (Uvicorn is localhost-only today — laptop admin = SSH or change bind in a separate decision.)

### Q5 — `/h5` on glass

| | |
| --- | --- |
| **A** | Same Chromium — header **H5** works; accept three-pane on touch. |
| **B** | Hide H5 link when `?embed=1` / kiosk UA; H5 is laptop-only. |
| **C** | H5 opens in a second window (bad for `--kiosk`). |

**Recommendation:** **A** — already shipped; tune layout only if glass litmus fails.

---

## Confirmed

_(empty until Round 1 closes)_

## Later (blocked)

- Install script enablement + flat `~/bhvr-nvr` paths.
- Cursor hide / labwc rules.
- Bind uvicorn on LAN vs SSH-only admin.
- Optional “fewer auto-LIVE” kiosk profile (performance policy, not embed chrome).
