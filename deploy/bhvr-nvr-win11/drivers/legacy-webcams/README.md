# Legacy Class_FF webcam drivers (Win11 kit)

Offline driver packs for **vendor-class** USB sticks that do **not** bind
inbox `usbvideo.sys` (Compatible ID `USB\Class_FF…`). Copy this folder to the
target Win11 NVR and run the installer elevated.

These are **not** preferred for a 4-cam cage fleet. Prefer UVC sticks that
advertise **MJPEG** (or H.264) in DirectShow. YUYV-only and Class_FF chips are
kept here only so random drawer cams can be identified and tested.

## Packs in this kit

| Folder | USB ID | Chip / brand | INF | Notes |
| --- | --- | --- | --- | --- |
| `vimicro_0ac8_301b/` | `VID_0AC8` `PID_301B` | Vimicro ZC0301PL | `usbvm31b.inf` | USB 1.1-era; VGA often capped ~6 fps |
| `pixart_093a_2468/pkg/` | `VID_093A` `PID_2468` (also `2472`) | Pixart PAC207 / Genius Eye 110 | `PFC027.inf` | Shows as “CIF Single Chip” until driven |

Zips kept next to the extracted trees for re-copy:

- `vimicro_0ac8_301b/ZC0301-301-4-328-07.zip`
- `pixart_093a_2468/Eye110_Windows.zip`

SHA-256 of those zips: see `MANIFEST.sha256.txt`.

## Install (target Win11 PC)

1. Copy `legacy-webcams/` onto the machine (USB stick / sync).
2. Plug the orphan camera(s) so Device Manager shows Code 28 / unknown.
3. **PowerShell as Administrator**, from this folder:

```powershell
cd <path>\deploy\bhvr-nvr-win11\drivers\legacy-webcams
Set-ExecutionPolicy -Scope Process Bypass
.\Install-LegacyWebcamDrivers.ps1
# or one pack only:
.\Install-LegacyWebcamDrivers.ps1 -Pack vimicro
.\Install-LegacyWebcamDrivers.ps1 -Pack pixart
```

4. Confirm Device Manager: Image/Camera node **OK**, no yellow bang.
5. Check DirectShow:

```powershell
ffmpeg -hide_banner -list_devices true -f dshow -i dummy
```

### Manual fallback

Device Manager → unknown device → Update driver → Browse → point at the pack
folder that contains the `.inf` (and `.sys` / `.cat`).

## Caveats

- Packages are **2007–2009**, WHQL-catalog signed for their era. Win11 may still
  accept them (this desk did for Vimicro). If `pnputil` rejects the hash/catalog,
  do **not** casually enable `testsigning` on a lab NVR without a documented
  exception.
- Bundled helper EXEs (`Domino.exe`, `VMCap.exe`, `Monitor.exe`, …) are **not**
  required for capture. The install script only stages INF/SYS via `pnputil`.
  Do not run the vendor “setup” CD apps on a kiosk image.
- Class_FF + proprietary WDM ≠ UVC. Kiosk `local_uvc` may need per-VID pixel
  format quirks (already: `0ac8` → `bgr24`). Pixart untested in the LIVE path
  until bound on a desk.
- **4-up on one hub** still depends on USB isoch / compression. Binding more
  Class_FF sticks does not fix YUYV isoch limits.

## Adding another stick

1. Note Hardware ID from Device Manager (`USB\VID_xxxx&PID_yyyy`) and Compatible
   IDs (look for `Class_0E` = UVC vs `Class_FF` = vendor).
2. Create `deploy/bhvr-nvr-win11/drivers/legacy-webcams/<vendor>_<vid>_<pid>/`.
3. Drop vendor zip + extracted INF/SYS/CAT; append SHA-256 lines to
   `MANIFEST.sha256.txt`.
4. Extend `Install-LegacyWebcamDrivers.ps1` `$Packs` table.
5. Document formats (`ffmpeg -f dshow -list_options true -i "video=…"`).
