# bhvr-kiosk — session console (Pi NVR touchscreen)

Experimenter kiosk for **cage-night** recordings: NWB-oriented metadata →
session folder → live H.264 stream from cams onto the NVR SSD. Not Frigate, not HA.

## Roles

| Host | Role |
|------|------|
| `bhvr-nvr*` (Pi 4) | This console + Mosquitto + Invite beacon; **writes** session MPEG-TS |
| `bhvr-cam*` (Pi Zero W) | `rpicam-vid \| ffmpeg` MPEG-TS over SSH; keeps tiny `timestamps.pts` |

Science archive = `data_root[/subdir]/{tag}-<utc>/` with `{subject}__{tag}__{cam}__pNNN.ts` (default tag `ses`)
rolled by Session **chunk minutes**, packed into `{subject}__{cam}.h5`
(`video/mpegts_NNN` + `pts_NNN`; see `SETTINGS_GRILL.md`).

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
scp -r deploy/bhvr-kiosk deploy/bhvr-nvr-pi4b admin@bhvr-nvr0:~/deploy/
ssh admin@bhvr-nvr0
sudo bash ~/deploy/bhvr-nvr-pi4b/scripts/install_kiosk.sh ~/deploy/bhvr-kiosk
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

**Win11 local USB:** set `capture_backend: local_uvc` (see `../bhvr-nvr-win11/config.kiosk.example.yaml`). Skips MQTT; bind up to `local_uvc.max_concurrent` (default/soft 4) in Session settings — USB may still refuse 4-up on one uplink. LIVE v1: mpegts.js tiles via idle dshow→MPEG-TS publisher; REC tees the same TS bytes.

## Pairing

Invite → MQTT roster → Start session. See `../NETWORK.md`.

| Action | Doc |
|--------|-----|
| SSH trust (NVR key on cam) | [`../bhvr-cam-pi0w/ssh/README.md`](../bhvr-cam-pi0w/ssh/README.md) |
| Cam software deploy | [`../bhvr-cam-pi0w/CAM_SOFTWARE_DEPLOY.md`](../bhvr-cam-pi0w/CAM_SOFTWARE_DEPLOY.md) |
| Session vs planned Kiosk settings | [`SETTINGS_GRILL.md`](SETTINGS_GRILL.md) |
