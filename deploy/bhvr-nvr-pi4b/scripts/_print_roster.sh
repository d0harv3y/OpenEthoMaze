#!/bin/bash
curl -sS -m 5 http://127.0.0.1:8080/api/cams | python3 -c '
import sys, json
d = json.load(sys.stdin)
for c in sorted(d.get("cameras") or [], key=lambda x: x.get("id") or ""):
    print(c.get("id"), c.get("online"), c.get("link"), c.get("ip"))
'
