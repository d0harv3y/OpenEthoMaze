# Grill Mode 1 ↔ wireless auto-switch and kiosk override

Type: grilling  
Status: open  
Blocked by:

## Question

What are the exact semantics for **automatic backhaul preference** and **per-cam kiosk override**?

Must settle: detect USB up/down; delay/hysteresis on unplug; what happens to an active focus-live or record session on switch; override persistence (reboot? session?); interaction with MQTT announced IP. Output is a short decision record suitable for NETWORK.md / kiosk UX — not implementation in this ticket.
