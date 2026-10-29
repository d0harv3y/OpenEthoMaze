# bhvr-cam — Pi Zero W cage camera

H.264 capture + MQTT presence. Broker address learned from **NVR Invite**
(UDP beacon), not static IPs. Optional **HTU21D** on I2C (`/dev/i2c-1` @ `0x40`)
piggybacks env on the announce JSON (see `scripts/htu21d.py`):
**1 Hz** sample timer fills a 10-sample ring; announce **every 10 s** publishes
window **mean** (`temp_c` / `rh_pct`) plus `env.{temp_c,rh_pct}.{min,max,mean}` for
REC JSONL. Needs `dtparam=i2c_arm=on` + `i2c-dev` module.

**Primary backhaul:** USB gadget overnight + sessions (archive on NVR SSD).  
**WiFi soak:** short battery window; mode-switch announce — see [`../NETWORK.md`](../NETWORK.md).  
**Hotfix without re-flash:** [`CAM_SOFTWARE_DEPLOY.md`](CAM_SOFTWARE_DEPLOY.md) (≠ SSH trust, ≠ Invite).

**Slim firstboot** installs scripts + systemd only — **no apt**. Works on
air-gapped wsu-iot. Announce uses stdlib Python MQTT (no `mosquitto-clients`).
Runtime packages (`rpicam-apps`, **`ffmpeg`** for MPEG-TS / UDP live): bake into
`debs/` for firstboot, or hotspot + `install_runtime_pkgs.sh` — **not** WSU-IoT.
See [`offline/README.md`](offline/README.md).

## Preferred: zero-touch SD

1. Fill `debs/` once (offline README) + Imager (Lite 32-bit, `bhvr-camN`, **NVR** pubkey, wsu-iot).
2. **Before eject**, arm firstrun:

```powershell
cd C:\Users\admin\code\OpenEthoMaze\deploy\bhvr-cam\sd-boot
.\apply-to-boot.ps1 -BootDrive E:   # your boot drive letter
```

3. Boot the Zero — firstboot arms listen/announce; then NVR **Invite cameras**.

Details: [`sd-boot/README.md`](sd-boot/README.md).

## Manual fallback (USB/SSH)

```bash
scp -r deploy/bhvr-cam admin@<cam>:~/
sudo bash ~/bhvr-cam/firstboot/99-bhvr-cam.sh
# when the cam has internet (hotspot):
sudo bash ~/bhvr-cam/scripts/install_runtime_pkgs.sh
```

## Wired tether (USB gadget CDC ECM)

Cam presents as USB ethernet on the NVR (no Windows-style host driver on Pi OS).

```bash
# on cam (also part of slim firstboot)
sudo bash ~/bhvr-cam/scripts/install_usb_gadget.sh
sudo reboot   # if dtoverlay=dwc2 was newly added

# on NVR (once)
sudo bash ~/deploy/bhvr-nvr/scripts/install_usb_gadget_host.sh
```

Plug Zero **data** micro-USB → powered hub → NVR. Litmus: NVR `lsusb` shows a
gadget; `ip -br a` has `usb0`/`enx*` at `192.168.7.1`. See [`../NETWORK.md`](../NETWORK.md)
§ USB gadget.

## Scripts

| Command | Role |
|---------|------|
| `bhvr-cam-find-broker` / listen service | Wait for Invite beacon |
| `bhvr-cam-announce` | MQTT `…/state` (Python stdlib) |
| `bhvr-cam-record` | 720p30 / 720p20 / 480p30 (needs `rpicam-vid`; writes `.h264`) |
| `install_runtime_pkgs.sh` | Online apt: `rpicam-apps` + `ffmpeg` (+ optional mosquitto-clients) |

Wired fallback (wlan ↔ USB gadget / USB-Ethernet): [`../NETWORK.md`](../NETWORK.md) § Wired fallback.

