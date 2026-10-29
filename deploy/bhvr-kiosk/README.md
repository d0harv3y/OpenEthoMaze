# bhvr-kiosk — session console (Pi NVR touchscreen)

Experimenter kiosk for **cage-night** recordings: NWB-oriented metadata →
session folder → live H.264 stream from cams onto the NVR SSD. Not Frigate, not HA.

## Roles

| Host | Role |
|------|------|
| `bhvr-nvr*` (Pi 4) | This console + Mosquitto + Invite beacon; **writes** session MPEG-TS |
| `bhvr-cam*` (Pi Zero W) | `rpicam-vid \| ffmpeg` MPEG-TS over SSH; keeps tiny `timestamps.pts` |

Science archive = `data_root[/subdir]/ses-<utc>/` with `{subject}__{cam}__pNNN.ts` (see `SETTINGS_GRILL.md`). H5 pack is next slice.

**Why not write video on the cam?** Local multi-GB then `rsync` at Stop was a litmus path; wireless batch pull timed out / filled the Zero. Acquisition now pipes stdout to the NVR so the cam disk stays near-empty.

## Live preview

Science + live share one wire: cam **HW H.264** → **ffmpeg copy-remux MPEG-TS** → SSH →
NVR tees to `*_video.ts` and the browser (mpegts.js). Timing truth stays `--save-pts`.

| `preview.transport` | Idle | While recording |
|---------------------|------|-----------------|
| `mpegts` (Mode 2 soak) | HTTP MPEG-TS (mpegts.js) | same TS byte-tee (no NVR remux) |
| `whep` | MediaMTX WHEP | TS byte-tee (idle WHEP stops) |
| `udp` / `webrtc` | legacy UDP / aiortc | TS byte-tee |

Cam needs `~/bin/ffmpeg`. Set `preview.nvr_host` if ingress autodetect is wrong.

Tunables: `config.yaml` → `preview:` (`transport`, `udp_port`, `width`, `fps_idle`, …).

```bash
# from laptop (example)
scp -r deploy/bhvr-kiosk deploy/bhvr-nvr admin@bhvr-nvr0:~/deploy/
ssh admin@bhvr-nvr0
sudo bash ~/deploy/bhvr-nvr/scripts/install_kiosk.sh ~/deploy/bhvr-kiosk
```

Then authorize the printed NVR pubkey on each cam. Cams need `rpicam-vid`
and `bhvr-cam-record.service` (slim firstboot installs the unit).

## Dev on any machine

```bash
cd deploy/bhvr-kiosk
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

## Config

`config.example.yaml` → `config.yaml`. Set `ssh_identity_file` to the NVR key.

## Pairing

Invite → MQTT roster → Start session. See `../NETWORK.md`.

| Action | Doc |
|--------|-----|
| SSH trust (NVR key on cam) | [`../bhvr-cam/ssh/README.md`](../bhvr-cam/ssh/README.md) |
| Cam software deploy | [`../bhvr-cam/CAM_SOFTWARE_DEPLOY.md`](../bhvr-cam/CAM_SOFTWARE_DEPLOY.md) |
| Session vs planned Kiosk settings | [`SETTINGS_GRILL.md`](SETTINGS_GRILL.md) |
