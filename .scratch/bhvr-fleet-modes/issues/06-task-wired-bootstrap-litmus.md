# Task: wired bootstrap litmus (MQTT + SSH)

Type: task  
Status: open  
Blocked by:

## Question

_(Task — prove Destination’s first slice.)_

Define and run a **wired bootstrap litmus** on at least one cam (prefer cam1; cam0 when available):

1. Imager + `apply-to-boot` (or equivalent already armed).
2. USB gadget link to NVR (`192.168.7.0/24`).
3. Cam appears on kiosk MQTT roster with gadget IP.
4. NVR → cam SSH works with `id_ed25519_bhvr` (BatchMode), no password, no SD pull.

Done when: checklist is written into deploy docs (or linked from NETWORK.md) and litmus has passed once. Focus-live fps is **out of scope** for this ticket.
