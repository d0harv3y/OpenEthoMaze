# Cam software deploy

Push updated scripts from an NVR onto **already-trusted** cams over USB (or WiFi
SSH), then install into `/usr/local/bin`. This is **not** SSH trust and **not**
Invite.

| Term | What it does |
|------|----------------|
| **SSH trust** | NVR public key → cam `authorized_keys` (Imager / firstboot / `ssh/nvr_authorized_keys`) |
| **Invite** | UDP beacon → cam caches MQTT broker (`broker.env`) |
| **Cam software deploy** | Copy + install cam scripts (e.g. `bhvr-cam-announce`) onto a running unit |

MQTT announce can work with only Invite + USB gateway. **LIVE / REC need SSH trust.**
Deploy needs SSH trust already in place (BatchMode key), plus **sudo on the cam**
to write root-owned `/usr/local/bin` (unless NOPASSWD is configured for that path).

## When to use

- Hotfix (mode-switch announce, HTU, record helpers) without re-flashing SD.
- After editing `deploy/bhvr-cam/scripts/*` on the laptop → NVR → cams.
- Prefer **USB** (`192.168.7.x`): fast, no IoT flakiness.

For **new** cams (4–7, nvr1 fleet): bake scripts + NVR pubkey(s) into the SD via
[`sd-boot/README.md`](sd-boot/README.md) / firstboot so you skip hand deploy.
You still **Invite** (or plug USB) once for the broker.

## Manual deploy (NVR shell today)

Staging file on NVR (example announce):

```bash
# laptop → NVR
scp deploy/bhvr-cam/scripts/announce_mqtt.py admin@bhvr-nvr0:/tmp/announce_mqtt.py
```

On NVR — **`-t` required** so `sudo` can prompt (plain `ssh` has no TTY):

```bash
# target shell: bash on bhvr-nvr*
for ip in 192.168.7.41 192.168.7.27 192.168.7.31 192.168.7.28; do
  echo "=== $ip ==="
  scp -i ~/.ssh/id_ed25519_bhvr -o IdentitiesOnly=yes /tmp/announce_mqtt.py admin@$ip:/tmp/
  ssh -t -i ~/.ssh/id_ed25519_bhvr -o IdentitiesOnly=yes admin@$ip \
    'sudo tee /usr/local/bin/bhvr-cam-announce >/dev/null </tmp/announce_mqtt.py \
     && sudo chmod 755 /usr/local/bin/bhvr-cam-announce \
     && sudo python3 /usr/local/bin/bhvr-cam-announce'
done
```

Litmus: announce JSON includes expected fields (`link`, `ips`, …); timer keeps
publishing every 10 s (`bhvr-cam-announce.timer`).

Helper (non-interactive bits only): `../bhvr-nvr/scripts/_deploy_mode_switch.sh`
still needs cam sudo for `/usr/local/bin`.

## Multi-NVR (nvr0 / nvr1)

| Need | How |
|------|-----|
| Cam accepts SSH from nvr1 | Merge **nvr1** pubkey into cam `authorized_keys` (SD bake both keys, or deploy-time append) |
| Cam talks MQTT to nvr1 | Invite from nvr1, or USB to nvr1 (`broker` = `192.168.7.1` on that host) |
| Same announce binary | Cam software deploy (or SD bake) — script is NVR-agnostic |

One cam may trust several NVRs; it should use **one** broker at a time.

## Planned: kiosk “Push cam update (wired)”

See [`../bhvr-kiosk/SETTINGS_GRILL.md`](../bhvr-kiosk/SETTINGS_GRILL.md) § Kiosk settings.
Goal: operator triggers deploy over USB from the UI without a laptop loop;
SSH trust remains SD/firstboot, not this button.

## Related

- SSH trust: [`ssh/README.md`](ssh/README.md)
- Firstboot / SD: [`sd-boot/README.md`](sd-boot/README.md), `firstboot/99-bhvr-cam.sh`
- Backhaul / mode-switch: [`../NETWORK.md`](../NETWORK.md)
- Fleet language: [`../GLOSSARY.md`](../GLOSSARY.md)
