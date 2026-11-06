#!/bin/bash
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json, sys
for c in json.load(sys.stdin).get("cameras", []):
    print(c.get("id"), c.get("link"), "online="+str(c.get("online")),
          "age="+str(c.get("age_s")), "ip="+str(c.get("ip")), "ips="+str(c.get("ips")))
'
