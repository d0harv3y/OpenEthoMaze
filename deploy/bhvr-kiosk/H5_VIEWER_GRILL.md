# In-kiosk H5 viewer grill

Do not contradict without a new grill round.

- **Status:** Rounds 1–4 confirmed 2026-11-02. **MVP implemented** 2026-11-02 (`/h5`, `/api/h5/*`, Pack now).
- **Parked (later grill):** batch export → MP4 + sidecar metadata table; migrate network backup onto `/h5` (keep-H5 vs MP4+table, network pathing). No MVP stub (Q13=A).
- **Related:** [SETTINGS_GRILL.md](SETTINGS_GRILL.md); [LIVE_REC_PROTOCOL_GRILL.md](LIVE_REC_PROTOCOL_GRILL.md).

## Scope in (MVP)

- Page **`/h5`** (header link **H5**; ← Console → `/`). No video wall.
- Sessions → cam `*.h5` + deep-link `/h5?session=&file=`.
- Three panes: sessions/files | tree + attrs/preview | player.
- Server h5py; raw `video/mpegts_NNN` stream (`video/mp2t`, optional Range).
- Part dropdown (one part at a time; default = lowest index present).
- Non-video: attrs + capped text (~256 KiB) / small pts table.
- **Pack now** (whole session folder): each cam’s loose `.ts` → **that cam’s** H5; background `pack_jobs`; skip existing datasets by default, **Force** to overwrite; delete loose after verify.
- Active session folder: refuse open of its H5s (409).
- Path sandbox: realpath under `data_root`; name ids only.

## Scope out

- Write/edit/delete H5; maze `trials.h5`; full spreadsheet UI; h5wasm.
- Download `.h5` / Export / Backup UI (later grill).
- Play-all / cross-part seek / timeline.
- Moving Kiosk settings off console.

## Facts

- One H5 per cam: `{subject}__{tag}__{cam}.h5` with `video/mpegts_NNN`, `pts_NNN`, `logs/*`, `description` attrs.
- `GET /api/kiosk/sessions` lists folders; no `/api/h5/*` yet.
- Player: existing `static/mpegts.min.js`.

---

## Confirmed

| # | Decision | Choice |
| --- | --- | --- |
| Q1 | MVP job | **C** — tree + attrs + video |
| Q2 | Surface | **B** — `/h5` page |
| Q3 | Read stack | **A** — server h5py |
| Q4 | During REC | **A** — refuse active target (folder-level via Q14) |
| Q5 | Picker | **C** — sessions → files + deep-link |
| Q6 | Multi-part | **A** — part dropdown |
| Q7 | Stream | **A** — raw + Range |
| Q8 | Non-video | **A** — attrs + capped preview |
| Q9 | Loose TS | **C** — Pack now |
| Q10 | Pack now shape | **B** — whole session → **per-cam** H5s |
| Q11 | Chrome | **A** — three panes |
| Q12 | Sandbox | **A** — realpath under `data_root` |
| Q13 | Extras | **A** — no download / no backup stub |
| Q14 | Active refuse UX | **A** — block whole active folder’s H5s |
| Q15 | Pack now idempotency | **C** — skip existing; **Force** overwrites |

### Implementation defaults (accepted)

- Header link label: **H5**.
- Default part: lowest index present.
- Text preview cap: **256 KiB**.
- Pack now deletes loose after verify (`delete_loose=True`).

---

## Future (out of this grill)

- Batch export → MP4 + sidecar metadata table.
- Network backup on `/h5`: keep-H5 vs MP4+table; UNC/pathing (migrate from Kiosk settings).
- Download `.h5` / extracted `.ts`.
- Play-all / timeline; per-cam active refuse; Kiosk settings as its own page.
