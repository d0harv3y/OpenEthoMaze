# CapturePort contract (MULTIHOST grill Q6–Q9)

Invariants every capture adapter must honor so Pi-today and Win-tomorrow write the **same** science archive. Companion code: `app/capture_port.py`.

## Non-goals

- Dual encode / MediaMTX on Windows (LIVE v2 / WHEP on Win).
- Replacing Pi SSH acquisition in this document.
- Docker packaging.
- LAN auth for the kiosk UI.

## H5 / session invariants (unchanged)

- Session folder: `{tag}-<utc>/` under `data_root`[/subdir].
- Per-cam archive: `{subject}__{tag}__{cam}.h5`.
- Video: `video/mpegts_NNN` (uint8 MPEG-TS), optional `video/pts_NNN`.
- Adapter delivers **MPEG-TS bytes** (+ optional pts); it owns encode/remux (grill Q6=A).

## CapturePort (REC)

Minimal surface:

| Method | Role |
| --- | --- |
| `list_sources()` | Discover cams with **stable `source_id`** (USB serial / VID:PID+port on UVC; MQTT id on Pi). |
| `open(source_id, cam_id)` | Bind hardware source → operator `cam_id` (filename token). |
| `start_record(cam_id, sink)` | Begin writing MPEG-TS to `RecordSink` (path or callback). |
| `stop_record(cam_id)` | Stop cleanly; flush. |
| `snapshot_jpeg(cam_id) -> bytes \| None` | Optional still (diagnostics); tiles use LivePort. |

`RecordSink` receives append-only TS bytes and optional pts lines/file. Optional `on_ts_bytes` tees the same chunks to LIVE.

## LivePort (local_uvc LIVE v1)

Upgrade ladder (grill Q7):

1. Crude: JPEG / external viewer (shipped, retired for tiles).
2. **LIVE v1 (current):** idle dshow→libx264 MPEG-TS publisher + science `on_ts_bytes` tee → `GET /api/preview/{cam}` → mpegts.js.
3. Optional second encode / MediaMTX only if measured need (LIVE v2).

Idle LIVE spends the same USB isoch budget as REC; expect ≤3 solid tiles per uplink.

## Identity (Q8=A)

- Prefer OS-stable USB identity; never use friendly name alone as primary key.
- Config may map `source_id` → display `cam_id`.
- Desk litmus (2026-11-03): **3× simultaneous** YUYV UVC on **one uplink** is the accepted ceiling; **4×** failed isochronous reservation (not average bandwidth). Independent of full UI.

## Adapters

| Adapter | Host | Sources |
| --- | --- | --- |
| `PiCamSSH` (today’s behavior, wrap later) | Pi4 / future Win | `bhvr-cam-pi0w` over SSH |
| `LocalUvc` | Win11 (`capture_backend: local_uvc`) | DirectShow YUYV → encode → TS; soft ≤4 bind (USB may refuse 4-up) |
| `FakeCapture` | tests | Synthetic TS |

## Host trees

| Tree | Role |
| --- | --- |
| `deploy/bhvr-kiosk` | Multi-platform controller |
| `deploy/bhvr-cam-pi0w` | Pi Zero W appliance |
| `deploy/bhvr-nvr-pi4b` | Pi 4 NVR appliance |
| `deploy/bhvr-nvr-win11` | Windows host appliance (stub → spike) |
