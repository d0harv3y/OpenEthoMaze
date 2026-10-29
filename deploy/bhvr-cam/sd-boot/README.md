# Zero-touch SD bring-up (no USB required)

After Raspberry Pi Imager writes the card, **before you eject**, run
`apply-to-boot.ps1` against the visible **boot** drive (FAT32, has `cmdline.txt`).

## Steps

1. **Once per OS release:** fill `deploy/bhvr-cam/debs/` with armhf packages
   (`rpicam-apps`, `ffmpeg`, …) — see [`../offline/README.md`](../offline/README.md).
   WSU-IoT cannot be trusted for apt.
2. Imager: Lite 32-bit, hostname `bhvr-camN`, user `admin`, **WSU-IoT** Wi‑Fi +
   country. Still paste NVR pubkey in Imager if you can; **`apply-to-boot` also
   bakes** `ssh/nvr_authorized_keys` via firstboot + `user-data` merge (see
   [`../ssh/README.md`](../ssh/README.md)).
3. When Imager finishes, note the boot drive letter (e.g. `E:`).
4. From PowerShell on your PC:

```powershell
cd C:\Users\admin\code\OpenEthoMaze\deploy\bhvr-cam\sd-boot
.\apply-to-boot.ps1 -BootDrive E:
```

5. Eject safely, power the Zero. First boot:
   - runs `bhvr-firstrun.sh` (via `cmdline.txt` systemd.run)
   - installs **NVR `authorized_keys`** (focus/record SSH)
   - disables **avahi-daemon**
   - `dpkg -i` anything in `bhvr-cam/debs/` (offline; keep empty on Zero until
     Raspbian-v6-only set exists)
   - installs listen + announce + USB gadget
   - strips the cmdline hook (even if install fails)
   - reboots once
6. Check boot FAT `bhvr-net-status.txt` → `result=ok`. Then NVR **Invite cameras**
   (or USB tether; announce can use gadget DHCP gateway).

Without `debs/`, live needs USB-pushed `~/bin/ffmpeg` (static) until a safe bake exists.

**cam0 already booted without NVR key:** pull the card, re-run `apply-to-boot.ps1`
(re-arms firstrun + merges keys), boot once, then focus live.

## What gets copied onto boot

| Path on card | Role |
|--------------|------|
| `bhvr-cam/` | full payload (`firstboot/`, `scripts/`, `systemd/`) |
| `bhvr-firstrun.sh` | oneshot installer |
| `cmdline.txt` | gains `systemd.run=/boot/firmware/bhvr-firstrun.sh …` |

## Debug

- `bhvr-firstrun.log` on the boot partition after a run  
- `bhvr-net-status.txt` — WiFi wait + routes (`result=ok`, `wlan0_ipv4=…`,
  `default_via=…`, `default_dev=…`, full `ip route` / `iw` / DNS dump)  
- If firstrun never runs: confirm `cmdline.txt` still contains `systemd.run=`  
- Fallback: USB/SSH and `sudo bash ~/bhvr-cam/firstboot/99-bhvr-cam.sh`
