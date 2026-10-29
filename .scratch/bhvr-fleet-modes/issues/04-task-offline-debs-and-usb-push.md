# Task: offline debs bake + USB push path

Type: task  
Status: blocked  
Blocked by: raspbian-armv6-only deb fetch (NVR multiarch mixed Debian armv7 → Zero SIGILL)

## Question

_(Task — unblock Mode 1 live packages without WSU-IoT apt.)_

Produce a working **fleet package path**:

1. Fetch armhf `rpicam-apps` + `ffmpeg` (and deps) into `deploy/bhvr-cam/debs/` from a network that can reach RPi mirrors (not WSU-IoT).
2. Confirm `apply-to-boot.ps1` + firstboot `dpkg -i` install them on a fresh card.
3. Document **USB push** (`scp` + `dpkg`) for an already-bootstrapped cam (cam1).

Done when: a written recipe exists and at least one path (bake or USB push) has been demonstrated, with sizes noted vs local-store budget. Does not require focus-live green.

## Comments

### Progress 2026-10-14

- Campus `apt` on cam1 fails (mirror/DNS); interim **johnvansickle static armhf ffmpeg** (~32 MB) still usable without root.
- **Fetch (NVR):** armhf Inst set for `ffmpeg` + `rpicam-apps` via `_cam_apt_sim_list.sh` + `_fill_missing_armhf_debs.sh` → **194 debs / 132 MB** in `~/bhvr-debs` and `deploy/bhvr-cam/debs/` (gitignored).
- **Bake demonstrated:** copied onto `E:\bhvr-cam\debs\` (bootfs; ~280 MB free after). Firstboot already does `dpkg -i` when `debs/*.deb` present (`99-bhvr-cam.sh`). Fresh cards: `apply-to-boot.ps1 -BootDrive X:`.
- **USB push demonstrated:** `scp` of 194 debs → cam1 `~/bhvr-debs/` via `_usb_push_debs_to_cam.sh`. `dpkg -i` needs cam sudo (no NOPASSWD yet) — recipe in `deploy/bhvr-cam/offline/README.md`.
- Recipe + sizes documented in `offline/README.md`.
- **Regression:** that Inst set included Debian **ARMv7** libs → Zero **SIGILL**; cam1 live fail. Tainted `debs/` wiped from repo. Ticket reopened/blocked until Raspbian-v6-only fetch (or static-ffmpeg-only bake). cam0 → re-image, apply-to-boot **without** those debs.
