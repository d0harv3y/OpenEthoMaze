# bhvr-nvr-win11

Windows 11 **host appliance** for local USB (UVC) capture into the shared
`bhvr-kiosk` controller / H5 archive.

Status: **spike measured** (MULTIHOST grill). Adapter: `bhvr-kiosk/app/capture_uvc_dshow.py`.

### Accepted limit (2026-11-03)

**3 concurrent YUYV UVC streams per USB uplink** (one root-hub periodic schedule).
Do not promise 4-up on one hub/chain with these sticks. 4+ needs another root
controller, MJPEG/H.264 cams, or a non-dshow path — out of scope until revisited.

### Wire into kiosk (`capture_backend: local_uvc`)

```powershell
# from repo root — copy example, edit data_root, then run kiosk
copy deploy\bhvr-nvr-win11\config.kiosk.example.yaml deploy\bhvr-kiosk\config.yaml
# mkdir data_root if needed; ffmpeg on PATH
cd deploy\bhvr-kiosk
uv run uvicorn app.main:app --host 127.0.0.1 --port 8080
# browser → http://127.0.0.1:8080
# Session settings → bind ≤3 UVC sources → Apply UVC bindings → reload → Start
```

Spike scripts (pre-kiosk litmus):

```powershell
python deploy/bhvr-nvr-win11/scripts/spike_uvc_list.py
python deploy/bhvr-nvr-win11/scripts/spike_uvc_hub4.py --n 3 --seconds 8
python deploy/bhvr-nvr-win11/scripts/spike_uvc_rec_h5.py --seconds 5 --snapshot
```

### Litmus (this desk, 2026-11-03)

Hardware: 4× `vid_1871`/`pid_0306` YUYV-only sticks (160/320/640 @30; **no MJPEG**) + laptop `vid_04f2`. Same ceiling on a second Genesys hub chain (still one `ROOT_HUB30` uplink).

| Check | Result |
| --- | --- |
| List stable `usb:vid_…#inst` | PASS |
| Solo REC / JPEG / H5 pack | PASS |
| **3× simultaneous** @320×240 | **PASS** → **accepted product ceiling** |
| **4× simultaneous** @160 or 320 | **FAIL** (4th open: could not run graph) |

Cause: USB **isochronous reservation** (periodic schedule), not average MiB/s and not app buffers.

See `../bhvr-kiosk/MULTIHOST_GRILL.md` and `../bhvr-kiosk/docs/capture_port.md`.

### Legacy Class_FF drawer cams

Offline drivers + install script for non-UVC sticks (Vimicro `0AC8:301B`,
Pixart/Genius `093A:2468`): [`drivers/legacy-webcams/`](drivers/legacy-webcams/).
Copy that folder to another Win11 box and run `Install-LegacyWebcamDrivers.ps1`
elevated. Prefer MJPEG UVC cams for multi-cam; these packs are last-resort.
