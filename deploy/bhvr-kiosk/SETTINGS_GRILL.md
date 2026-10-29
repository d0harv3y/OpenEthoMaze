# Kiosk / session settings grill

Do not contradict without a new grill round.

- **Session / layout / H5:** confirmed 2026-10-22  
- **Kiosk settings menu:** confirmed 2026-10-23 (Rounds 1–4)

## Layout & chrome

- Tiles first; minimal header; no-scroll target for embed.
- Header: title · roster + Invite · UTC / Local stacked · Start / Stop · **Session settings** · **Kiosk settings** · compact REC timer + science chip while recording.
- Honesty / REC≠LIVE copy: only while REC.
- Context menu: Live on/off · Session settings · Cam metadata · Start/Stop REC.

## Session settings

- Science size + soft fps drive **idle encode** too (LIVE “fart” visible before REC); disk still outperforms LIVE (REC banner).
- Size/fps editable idle; **locked while REC**.
- `maxlat`: UI + **localStorage** (per browser).
- Output: show `data_root` + pick **subdir under it**; warn if SSD unmounted (banner + block Start/Apply).
- Estimates: bitrate table pre-start + live `write_Bps` during REC.
- Chunk minutes: one field + presets Lite default / Standard default; defaults **20 / 5**; **`0` = no limit**.
- Fresh operator defaults: **Lite @ 30** (chunk 20).

## Per-cam metadata

- Per-cam: subject_id, cage_id, sex, strain; notes = tooltip only.
- Tile: empty/`—` until set, then subject · cage · sex · strain.
- **subject_id frozen once REC starts**; other fields still editable.
- Lite 648×486: out of scope (circle back).

## Files & H5

- Layout: `ses-<utc>/`; `{subject_id}__{cam_id}__p{NNN}.ts`.
- One H5 per cam with `video/mpegts_000`…; **no session JSON**; rich H5 attrs.
- H5 **created at REC start** (shell + attrs); roll loose TS by time limit; **background pack** after each roll; remainder at Stop.
- After verify: **delete** loose `.ts` / `.pts` for that part.
- H5 v0: raw MPEG-TS + pts + fps summary + attrs (session/part/pack UTC; pts relative). No Stop remux to MP4.

## Non-goals (session / H5 pass)

- Dual encode for cheap preview; rewrite kiosk language; Lite 648×486; maze `trials.h5` bridge.

---

## Kiosk settings (confirmed 2026-10-23 — built: `/api/kiosk/*` + header modal)

Distinct from **Session settings** (science size / fps / chunk / session subdir).
Header button **Kiosk settings** — NVR-wide / fleet ops.

### Panels (v1)

| Panel | Intent | Confirmed behavior |
|-------|--------|-------------------|
| **USB push updates** | Soft deploy to ONLINE·USB cams | See § USB push |
| **SSID & password** | Same lab Wi‑Fi profile → cams **and** NVR | See § Wi‑Fi |
| **Network backup** | On-demand CIFS copy of selected sessions | See § Backup |
| **Data root** | Absolute archive root (SSD swap) | See § Data root |

Doc: [`../bhvr-cam/CAM_SOFTWARE_DEPLOY.md`](../bhvr-cam/CAM_SOFTWARE_DEPLOY.md). Not Invite, not SSH trust, not SD bake.

### USB push

- **Targets:** ONLINE · USB + BatchMode SSH litmus OK; this NVR’s `id_ed25519_bhvr` only; checklist (all eligible checked by default) + per-cam log.
- **Contents (soft fleet set):** firstboot scripts/units — announce, find-broker, clean-broker-override, HTU reader + sample timer/units, record helper, broker-listen unit, announce timer/units, USB **gadget files/units as files only**. Not OS/debs. Not a full gadget reinstall mid-push.
- **Source tree:** git checkout of **OpenEthoMaze** on the NVR (one repo — `deploy/bhvr-cam` is a folder, not a nested git). Default `$HOME/OpenEthoMaze` with config override. Version = `git describe` / short SHA; **dirty OK** with warning.
- **Cam sudo:** firstboot `/etc/sudoers.d/bhvr-cam` NOPASSWD for `tee` / `chmod` / `mkdir` / `cp` / `systemctl` (extend if missing on older images).
- **Deferred:** separate **Repair USB** (run gadget install / bounce) — not part of Push.

### Wi‑Fi (SSID & password)

- One form: SSID + password (+ optional hidden-network); NM connection name fixed `bhvr-iot`.
- Apply to **cams and NVR** (same campus/lab profile). Warn if operator is on IoT-only when changing **NVR** Wi‑Fi.
- **Order:** cams first (USB push of NM profile), **NVR last**.
- Secrets: write-only UI; persist NVR copy in root-only file (e.g. `/etc/bhvr/wifi.env`); never echo PSK back via API.

### Network backup

- **Manual “Backup now” only** (no post-Stop hook in v1).
- Modal: UNC + user + password (**re-enter every time** — not stored) → list `ses-*` under data_root → multi-select → mount → copy → unmount + progress.
- Example share shape: `\\cs.spokane.wsu.edu\Davis-Lab\…\bhvr-backup`.

### Data root

- Show path + mount health; edit absolute `data_root` in `config.yaml` (rare SSD swap).
- **Apply** → write config → UI offers **restart kiosk web** (uvicorn/unit). Session settings still pick **subdir under** data_root only.

### NVR privileges

- Kiosk backend needs scoped NOPASSWD/sudoers for Apply actions (`nmcli`, CIFS mount/umount, tee config, restart kiosk unit) — mirror cam appliance model. Do **not** run whole kiosk as root.
- **Embedded Chromium** (still TODO) does not change the privilege model; it only changes display chrome. Prefer wired/USB admin path when applying NVR Wi‑Fi from an embedded session.

### Out of scope (Kiosk settings menu)

- Per-cam animal metadata → Cam metadata.
- Science encode knobs → Session settings.
- Baking SD / Imager → laptop `apply-to-boot`.
- Post-session backup hook; Repair USB panel; dual-encode preview.

### Grill index (2026-10-23)

Q1=A header button · Q2=A four panels · Q3=A cam NOPASSWD · Q4=C cams+NVR same Wi‑Fi · Q5=A manual backup · Q6=A+C this key + litmus · Q7=A soft fleet set · Q8=A root-only wifi env · Q9=A cams then NVR · Q10=B session multi-select · Q11=B creds each time · Q12=A config.yaml + restart · Q13=A no gadget reinstall · Q14=B git checkout on NVR · Q15=A cam checklist · Q16=A SSID+password · Q17=A mount/copy/unmount modal · Q18=A `$HOME/OpenEthoMaze` (+ override) · Q19=A dirty OK · Q20=A Apply+restart · Q21=A NVR scoped sudoers.
