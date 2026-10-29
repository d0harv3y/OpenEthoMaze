# Offline / air-gap package install for bhvr-cam

WSU-IoT is flaky for DHCP and often **blocks apt mirrors**. Slim firstboot must
not depend on campus internet. Bake runtime `.deb`s onto the SD **boot**
payload so firstboot can `dpkg -i` them with zero WAN.

## What belongs on every card

| Need | How |
|------|-----|
| **WiFi profile** | Raspberry Pi Imager → WSU-IoT SSID/PSK + country US (empty NM connections = never joins) |
| **NVR SSH pubkey** | Imager *and/or* `apply-to-boot` → `ssh/nvr_authorized_keys` → firstboot `authorized_keys` (kiosk BatchMode) |
| **Hostname** | `bhvr-camN` |
| **Gadget + announce** | `apply-to-boot.ps1` → firstrun (`install_usb_gadget.sh`, MQTT listen/announce) |
| **`rpicam-apps`** | Local `debs/` (or image already has it — verify) |
| **`ffmpeg`** | Local `debs/` — required for kiosk `preview.transport: mpegts` (SSH→MPEG-TS). Annex-B works without it but is slow on Zero W @ 720p |
| **Optional** | `mosquitto-clients` (debug only; announce is stdlib Python) |

Firstboot already does best-effort:

```bash
dpkg -i "$TREE/debs"/*.deb || true
```

(`99-bhvr-cam.sh` — see that file.)

## Fetch debs (once per OS release)

Need a host that can reach `archive.raspberrypi.com` / `raspbian.raspberrypi.com`
(phone hotspot, home, lab VLAN, or the **NVR on Ethernet** — **not** WSU-IoT on the cam).

### Preferred: NVR (arm64) with armhf multiarch — no cam WAN

Fleet cams are **trixie / armhf**. The NVR already has `armhf` as a foreign arch and
mirror reachability. Demo path (2026-10-14):

```bash
# on NVR (admin@bhvr-nvr0), USB to a live cam for the Inst list:
bash deploy/bhvr-nvr/scripts/_cam_apt_sim_list.sh | tee /tmp/cam_inst_pkgs.txt
# recursive fetch (or fill missing) into ~/bhvr-debs — see
#   _fetch_armhf_debs_on_nvr.sh / _fill_missing_armhf_debs.sh
# prune to Inst set:
bash deploy/bhvr-nvr/scripts/_prune_debs_to_inst.sh ~/bhvr-debs /tmp/cam_inst_pkgs.txt
# on PC (PowerShell):
#   scp admin@NVR:/home/admin/bhvr-debs/*.deb deploy/bhvr-cam/debs/
```

Measured (2026-10-14): **194 `.deb` ≈ 132 MB** against a Lite trixie cam — **do not use
that tree on Pi Zero W**. NVR `apt-get download …:armhf` mixed in **Debian armhf (ARMv7)**
libs (`libgfortran`, OpenCV, …). Zero is **ARMv6** → `rpicam-vid` **SIGILL**, half-configured
`ffmpeg`, live badge **fail**. Recovery: `deploy/bhvr-nvr/scripts/_recover_cam1_dpkg_mess.sh`.

**Safe Mode 1 path on Zero until a Raspbian-v6-only fetch exists:** keep image
`rpicam-apps-core`; ship **johnvansickle static armel/armhf ffmpeg** to `~/bin/ffmpeg`
(USB push). Do **not** bake the full `rpicam-apps` meta (pulls OpenCV/Qt).

### Alt: native armhf Pi with sudo

```bash
# on matching Raspberry Pi OS Lite 32-bit (same major as fleet)
sudo bash deploy/bhvr-cam/scripts/fetch_offline_debs.sh
# → writes *.deb into deploy/bhvr-cam/debs/
```

Or manually:

```bash
mkdir -p ~/bhvr-debs && cd ~/bhvr-debs
sudo apt-get update
sudo apt-get install -y --download-only --reinstall \
  rpicam-apps ffmpeg
cp /var/cache/apt/archives/*.deb ~/bhvr-debs/
# copy tree to PC → OpenEthoMaze/deploy/bhvr-cam/debs/
```

Keep `debs/` out of git (local/cache only); `apply-to-boot.ps1` copies the whole
payload including `debs/` onto the FAT boot partition.

## Card recipe (success path)

1. **Imager** (Lite 32-bit): hostname, user `admin`, NVR pubkey, WSU-IoT, wireless LAN country.
2. Populate `deploy/bhvr-cam/debs/` from the fetch step (if not already).
3. **Before eject:**

```powershell
cd C:\Users\admin\code\OpenEthoMaze\deploy\bhvr-cam\sd-boot
.\apply-to-boot.ps1 -BootDrive E:
```

4. Boot Zero (USB power OK). Firstrun installs units + `dpkg` debs + USB gadget; reboot once.
5. Litmus on card/boot FAT: `bhvr-net-status.txt` → `result=ok` and a `wlan0_ipv4=…`.
6. NVR: **Invite cameras** (or USB tether — announce uses usb0 DHCP gateway).

## If WiFi still fails DHCP

PSK OK but “IP configuration could not be reserved” = campus lease timeout.
Profile exists after a successful `nmcli`; bump wait:

```bash
sudo nmcli connection modify WSU-IoT ipv4.dhcp-timeout 90
sudo nmcli connection up WSU-IoT
```

USB gadget remains the reliable bring-up / apt / rsync path when IoT is weather.

## USB push (already-bootstrapped cam)

When the card already ran firstrun (no re-image), push debs over USB CDC from the NVR:

```bash
# on NVR — cam at 192.168.7.27 (adjust), debs in ~/bhvr-debs
CAM=admin@192.168.7.27
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes)
ssh "${KEY[@]}" "$CAM" 'mkdir -p ~/bhvr-debs'
scp "${KEY[@]}" ~/bhvr-debs/*.deb "$CAM":~/bhvr-debs/
ssh -t "${KEY[@]}" "$CAM" 'sudo dpkg -i ~/bhvr-debs/*.deb'
# verify
ssh "${KEY[@]}" "$CAM" 'command -v ffmpeg; command -v rpicam-vid; dpkg -l ffmpeg rpicam-apps | tail -5'
```

Needs **sudo on the cam** (password or NOPASSWD). Without sudo, use the interim
userland static binary (`~/bin/ffmpeg` from johnvansickle) for Mode 1 live only.

## Online fallback (hotspot only)

```bash
sudo bash ~/bhvr-cam/scripts/install_runtime_pkgs.sh
```

Do **not** count on this on WSU-IoT.

## Smoke

```bash
command -v rpicam-vid
command -v ffmpeg
# NVR kiosk: preview.transport mpegts → focus live should move
```
