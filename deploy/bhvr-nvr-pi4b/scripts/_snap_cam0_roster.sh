#!/bin/bash
set +e
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("id")=="bhvr-cam0":
        print("online", c.get("online"), "age_s", c.get("age_s"))
        print("ip", c.get("ip"), "link", c.get("link"))
        print("ips", c.get("ips"))
        print("ts", c.get("ts"))
'
echo "--- retained mqtt ---"
mosquitto_sub -h 127.0.0.1 -t bhvr/cam/bhvr-cam0/state -C 1 -W 2 -v 2>&1 | head -2
echo "--- reachability ---"
ping -c1 -W2 192.168.7.41 >/dev/null && echo usb_ping=ok || echo usb_ping=FAIL
ping -c1 -W2 10.248.238.167 >/dev/null && echo wifi_ping=ok || echo wifi_ping=FAIL
echo "gadgets=$(lsusb 2>/dev/null | grep -c 1d6b:0104 || echo 0)"
