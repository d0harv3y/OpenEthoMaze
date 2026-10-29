# Network pairing — MQTT + UDP broker beacon (no static IPs)

## Flow

```text
kiosk [Invite cameras] --UDP burst :45454-->  cams (listen daemon) cache broker
cams                   --MQTT …/state ----->  Mosquitto on NVR
kiosk                  <-- subscribe -------  live id → IP roster
```

Beacon payload: `BHVR_MQTT_BROKER <ip> <port>` — **on-demand only** (button /
`systemctl start bhvr-broker-beacon` oneshot / `POST /api/beacon`), not a 30s spam loop.

- **No DHCP reservation** required for cams or NVR.
- Optional: set `MQTT_BROKER=` in `/etc/bhvr-cam.env` to override discovery.

## NVR

```bash
sudo bash ~/deploy/bhvr-nvr/install_mosquitto.sh
# mosquitto only; beacon is oneshot
sudo systemctl start bhvr-broker-beacon   # peer test
# or kiosk: Invite cameras
mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/+/state' -v
```

## Cam SD prep

1. Imager: Lite 32-bit, pubkey, hostname `bhvr-camN`, wsu-iot.  
2. Before eject: `deploy/bhvr-cam/sd-boot/apply-to-boot.ps1 -BootDrive X:`  
3. First boot = **slim** (scripts + units only; **no apt** — air-gap safe).  
4. NVR **Invite cameras**.

Recording (`rpicam-apps`) is a later step when packages are available.
USB/SSH + `firstboot/99-bhvr-cam.sh` remains a manual fallback.

## Litmus

1. NVR: `journalctl -u bhvr-broker-beacon -f` shows beacon lines.  
2. Cam: Invite writes `/var/lib/bhvr/broker.env` via listen service.  
3. NVR `mosquitto_sub -h 127.0.0.1 -t 'bhvr/cam/+/state' -v` shows JSON.

## Note on broadcasts

Some APs filter limited (`255.255.255.255`) and/or directed broadcasts.
Beacon now sends **both**. If cams still never get `broker.env`, prove MQTT
unicast with a one-shot override on the cam:

```bash
# from NVR after Invite failed — cam IP from bhvr-net-status.txt / AP DHCP
ssh admin@10.248.235.74
sudo tee -a /etc/bhvr-cam.env >/dev/null <<'EOF'
MQTT_BROKER=10.248.238.22
EOF
sudo systemctl start bhvr-cam-announce.service
```

If that shows up on `mosquitto_sub`, discovery (UDP) is the break — not MQTT.
Clear the override once Invite/UDP works:

```bash
sudo bhvr-cam-clean-broker-override
# or: sudo sed -i -E 's/^[[:space:]]*MQTT_BROKER=/# MQTT_BROKER=/' /etc/bhvr-cam.env
```

## Roadmap (after MQTT litmus)

1. Clean manual `MQTT_BROKER=` overrides (Invite-only).  
2. Runtime pkgs: `rpicam-apps` + `ffmpeg` — `bhvr-cam/scripts/install_runtime_pkgs.sh` or `offline/README.md`.  
3. NVR→cam SSH key: `bhvr-nvr/scripts/push_nvr_ssh_pubkey.py` + cam `authorized_keys`.  
4. Kiosk Start/Stop: SSH `rpicam-vid -o -` pipe → NVR writes session `*_video.h264` on SSD; pull only tiny `timestamps.pts`.  
5. `install_kiosk.sh` on nvr0; optional Chromium kiosk unit.  
6. USB gadget tether is the **overnight / session primary**; WiFi is short soak + discovery.  
7. Later: NeuroConv / NWB + DANDI (session folders are the handoff).

## Operating modes (fleet intent)

| Mode | When | Backhaul |
|------|------|----------|
| **Overnight / session (primary)** | Cage watch, kiosk LIVE, science REC → SSD | **USB gadget** (`192.168.7.0/24`) |
| **WiFi soak (battery)** | Unplugged cam, ~2–3 h on current packs | WSU-IoT (`10.x`); idle + LIVE + REC all in scope for litmus |
| **Discovery** | First boot / Invite | UDP beacon → MQTT; WiFi or USB |

Wired is the default reliable path. WiFi is real (not “monitor-only”), but
expect higher RTT and shorter battery life. Four simultaneous full-quality live
tiles on WiFi + Zero W is still **not** an honest promise — prefer USB for
multi-cam LIVE.

## USB ↔ WiFi mode-switching

Pi Zero W always has **wlan0**. The USB data connector is a second path
(gadget CDC ECM → NVR, or later USB-Ethernet dongle). WiFi can stay associated
in parallel (dual-homed).

### Modes

| Mode | Hardware | Cam iface | NVR / LAN | Use |
|------|----------|-----------|-----------|-----|
| **USB gadget** | Micro-USB data → NVR (powered hub OK) | `usb0` | NVR `br-bhvr` `192.168.7.1` | **Primary** overnight + REC |
| **USB-Ethernet** | OTG adapter + RJ45 dongle → switch | `eth0` | Lab switch | Future multi-cam wired |
| **WiFi only** | WSU-IoT | `wlan0` | AP | Battery soak; Invite/discovery |

**Disk FPS wins.** Live preview never gets a second encode. While any session
is recording: `max_live_full = 1` (tap-to-focus); grid = MQTT presence.

### Preference / hysteresis

| Path | Metric (example) | Announce rule |
|------|------------------|---------------|
| `usb0` (carrier up) | 100 | Active within ~5 s of plug |
| `wlan0` | 600 | Active ~10 s after USB carrier loss (+ up to 10 s announce tick) |

If announce stalls after unplug (tile **STALE** forever): broker was only
`192.168.7.1` with no `MQTT_BROKER_WIFI` — hit **Invite**, then redeploy announce
that preserves WiFi fallback (see `CAM_SOFTWARE_DEPLOY.md`).

Announce ignores **zombie** USB: gadget often keeps `carrier=1` after the NVR
unplugs; we require TCP reachability to the USB MQTT gateway (`192.168.7.1:1883`)
before treating USB as the active backhaul. On USB-down it also drops the stale
`default via 192.168.7.1 dev usb0` route and **binds MQTT to the active iface
IP** (wlan0 when failing over) with a ~2 s connect timeout + WiFi broker
fallback — otherwise dual-home routing can blackhole publishes for minutes
while the tile still shows retained **USB**.
MQTT `…/state` fields:

- `ip` — active backhaul (LIVE/REC SSH target)
- `link` — `usb` \| `wifi`
- `ips` — `{usb?, wifi?}` when present (debug / recovery re-resolve)

Optional cam env (`/etc/bhvr-cam.env`):

```bash
# auto (default) | wlan | usb
NET_PREFER=auto
```

- `auto` — carrier + hysteresis (above).  
- `wlan` / `usb` — lab debug pin (SSH escape hatch; no kiosk UI yet).  

Broker cache (`/var/lib/bhvr/broker.env`):

- USB carrier up → pin MQTT broker to usb0 DHCP gateway (`192.168.7.1`).  
- USB down → drop tether gateway from cache; use Invite / `MQTT_BROKER` (NVR IoT IP).

Kiosk: WiFi SSH `ConnectTimeout=30` (USB 15). **Mismatch** hosts (USB IP while
`link=wifi`, or the reverse) use `ConnectTimeout=3` and a single litmus try so
LIVE does not sit on a dead tether for 45–90 s after a good MQTT flip. Roster
`ip`/`link` change tears down idle WHEP so the next start uses the new path;
the browser re-attaches LIVE on usb↔wifi flips. If SSH litmus still fails →
`ONLINE · WiFi · no LIVE` (plug USB to recover).

WiFi WHEP settle is ~5 s (USB ~3 s) plus encode/SSH start — expect LIVE a few
seconds after ONLINE·WiFi, not tens of seconds, when power/WiFi stay up.

Operator: **plug cable** → USB within seconds; **unplug** → WiFi after ~10–20 s
(no reboot) **only if the Pi stays powered and `wlan0` stays associated**.

### Seamless USB ↔ WiFi (checklist)

| Layer | Requirement |
|-------|-------------|
| Power | 5 V must **not** come only from the data USB you unplug (battery / boost / separate PSU). If ICMP to the cam’s WiFi IP dies on unplug, software cannot failover. |
| Dual-home | Before unplug, roster `ips` has **both** `usb` and `wifi`; `MQTT_BROKER_WIFI` set (Invite once). |
| Announce | Zombie USB check + bind MQTT to active iface + WiFi broker fallback (`announce_mqtt.py`). |
| Trigger | `bhvr-cam-announce.timer` ~10 s (optional: udev/networkd hook for faster). |
| Litmus | `deploy/bhvr-nvr/scripts/_litmus_unplug_failover.sh` — polls roster **and** ICMP; distinguishes power/WiFi drop vs MQTT stuck. |

Litmus (legacy): `deploy/bhvr-nvr/scripts/_litmus_mode_switch_cam0.sh`.

Hotfix announce/scripts without re-flash: [`bhvr-cam/CAM_SOFTWARE_DEPLOY.md`](bhvr-cam/CAM_SOFTWARE_DEPLOY.md)
(SSH trust and Invite are separate). Planned kiosk menu for push-deploy / WiFi
creds / backup / data root: [`bhvr-kiosk/SETTINGS_GRILL.md`](bhvr-kiosk/SETTINGS_GRILL.md)
§ Planned — Kiosk settings.

### USB gadget (v1 backhaul) — CDC ECM

Pi Zero W is the **USB device**; NVR is the **USB host**. No Windows-style
host driver on Raspberry Pi OS — kernel `cdc_ether` / `usbnet` bind automatically
once the cam presents CDC ECM.

**Cam** (installed by slim firstboot via `scripts/install_usb_gadget.sh`):

```text
# /boot/firmware/config.txt
dtoverlay=dwc2

# systemd: bhvr-cam-usb-gadget.service → CDC ECM → usb0
# networkd: bhvr-usb0.network (DHCP, metric 100; NM leaves usb0 unmanaged)
# announce_mqtt: MQTT broker = usb0 DHCP gateway when Invite cache empty
```

Manual / existing card (or from NVR over link-local once SSH works):

```bash
# on cam
sudo bash ~/bhvr-cam/scripts/install_usb_gadget.sh
# reboot once if dtoverlay=dwc2 was just added
sudo reboot

# from NVR (password or bhvr key once on cam authorized_keys)
bash ~/deploy/bhvr-nvr/scripts/push_cam_usb0_dhcp.sh
# optional: admin@192.168.7.10 after first lease
```

**NVR** (once per console):

```bash
sudo bash ~/deploy/bhvr-nvr/scripts/install_usb_gadget_host.sh
# → br-bhvr @ 192.168.7.1/24 + DHCP; each cdc_ether (usb0, usb1, …) enslaved
#    (single-iface-on-usb0 layout could not address a second gadget)
```

**Litmus**

```bash
# NVR after plug (data micro-USB on Zero, powered hub OK)
lsusb          # expect Linux Foundation / CDC-ish gadget, not only hubs/SSD
ip -br a       # usb0 or enx… with 192.168.7.1
# Cam: usb0 has 192.168.7.x; announce uses that IP when it owns the default route
```

Invite/UDP broadcast often **does not** cross the gadget subnet. No static
IPs: NVR DHCP emits a router (`192.168.7.1`); cam `announce_mqtt` uses the
**usb0 DHCP gateway** as MQTT broker when Invite cache is empty.

Mosquitto already listens on all ifaces (`listener 1883`). Rsync / focus over
`usb0` avoids the campus AP for heavy pulls. Powered hub is preferred so the
NVR is not the sole 5 V source for several Zeros.

### USB-Ethernet dongle (v1.5 live grid)

Per cam: OTG adapter + USB NIC → PoE/switch next to cages. Same metric policy
(`eth0` preferred). Discovery can stay WiFi-first or move entirely on-LAN if
the switch is isolated — still no static cam IPs required if DHCP is local.

### Kiosk UI implications (4 cams)

```text
2x2 grid  = roster tiles (id, ip, profile, REC/idle)     # always
tap tile  = full-quality focus (max 1 while recording) # MediaMTX later
long-press = config / meta / destination folder
schedule  = session windows; live optional pre-roll only
```

Destination folder defaults to SSD mount when present
(` /media/admin/random/…` or `/data/bhvr`).

### Litmus (mode switch)

1. Cam plugged: roster `ip` in `192.168.7.0/24`, badge `ONLINE · USB`, LIVE works.  
2. Unplug: within ~30–45 s roster `ip` becomes `10.x`, `link=wifi`, `ips` has both
   briefly then wifi; NVR `ssh` to that IP works; LIVE then short REC.  
3. Replug: within ~5–15 s roster returns to USB; LIVE over USB.  
4. If WiFi SSH fails: badge honesty (`no LIVE`); plug USB recovers.

## Circle back (wlan / kiosk)

- **USB gadget CDC ECM** — cam + NVR host scripts landed (`install_usb_gadget*.sh`);
  litmus on hubbed fleet; announce uses usb0 DHCP gateway (no static MQTT_BROKER).
- **USB-Ethernet dongle → switch** — multi-cam wired without gadget/OTG limits.
- **Offline local-record mode** — cam writes `.h264`+`.pts` to local media; kiosk
  schedules start/stop (and later pull/rsync to NVR SSD). No live science pipe;
  overnight-friendly when WiFi is weather. Store-and-forward companion to
  `wlan_stream` / UDP preview.
- **UDP science archive** — if focus UDP stays healthy, try MPEG-TS UDP for
  session ingest (lossy OK; pts is truth) as a middle ground before wired.
