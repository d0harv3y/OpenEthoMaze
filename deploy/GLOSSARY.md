# Bhvr fleet (kiosk / NVR / cams)

Operating language for the cage-camera fleet, NVR host, and session kiosk.
Analysis/stats terms live under `docs/vocab/` — see root `GLOSSARY-MAP.md`.

## Language

**NVR**:
The lab host that runs Mosquitto, the kiosk app, and session storage (SSD).
_Avoid_: server, base station (unless talking to non-lab audiences)

**Kiosk**:
The operator UI and API on the NVR that shows the cam roster and controls sessions.
_Avoid_: dashboard, web UI (alone)

**Cam**:
A Pi Zero W unit that encodes cage video and announces itself to the NVR.
_Avoid_: node, client, edge device

**Mode 1 — Wired live**:
USB gadget backhaul with live focus stream and NVR-side archive; fleet primary for behavior-grade work.
_Avoid_: wired fallback, USB alternate (legacy NETWORK.md wording)

**Mode 2 — Wireless live**:
WSU-IoT backhaul with a low-rate live focus stream.
_Avoid_: WiFi primary overnight (until an explicit decision restores that phrase)

**Mode 3 — Wireless local-store**:
High-rate capture on cam media, kiosk status over WiFi, later NVR backup; spec-first on the fleet-modes map.
_Avoid_: offline mode (ambiguous), edge record (vague)

**Backhaul**:
The network path that carries control and/or video (USB gadget vs WSU-IoT).
_Avoid_: connection, link (alone)

**Bootstrap litmus**:
After flash/arm, USB to NVR yields MQTT roster presence plus passwordless SSH from NVR to cam.
_Avoid_: firstboot success (firstboot is only the install step)

**SSH trust**:
NVR public key installed on the cam (`authorized_keys`) so BatchMode SSH can run LIVE/REC.
Baked at Imager / firstboot (`ssh/nvr_authorized_keys`). _Avoid_: pairing (alone), auth (alone)

**Invite**:
On-demand UDP broker beacon from the kiosk/NVR; cams cache MQTT host in `broker.env`.
_Avoid_: pairing (alone), discover (alone)

**Cam software deploy**:
Copy/install updated cam scripts onto a running unit (e.g. `bhvr-cam-announce` → `/usr/local/bin`).
Requires existing SSH trust + usually cam sudo. Not SSH trust, not Invite.
See `bhvr-cam/CAM_SOFTWARE_DEPLOY.md`. _Avoid_: OTA (implies full image), push keys (wrong)

**Focus live**:
The kiosk tile preview stream for one cam.
_Avoid_: livestream (alone), preview (alone when mode matters)

**Science record**:
Session H.264 (+ pts) written toward NVR storage; achieved rate from pts, not soft_fps alone.
_Avoid_: recording (alone), capture (alone)

**Soft fps**:
Encoder frame-rate *request* to rpicam; not a published scientific claim.
_Avoid_: fps claim, locked fps
