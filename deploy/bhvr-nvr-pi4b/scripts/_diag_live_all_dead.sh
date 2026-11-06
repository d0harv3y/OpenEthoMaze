#!/bin/bash
set -uo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)

echo "=== health ==="
curl -sS -m 5 http://127.0.0.1:8080/api/health | python3 -m json.tool 2>/dev/null | head -40

echo "=== roster ==="
bash /tmp/_snap_roster.sh 2>/dev/null || curl -sS -m 5 http://127.0.0.1:8080/api/cams | head -c 500

echo "=== mediamtx ==="
systemctl is-active mediamtx 2>/dev/null || systemctl --user is-active mediamtx 2>/dev/null || true
pgrep -af mediamtx | head -5 || echo no_mediamtx
ss -lntp | grep -E '8889|1555' | head -20 || true

echo "=== whep/start each online cam ==="
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys,urllib.request
cams=json.load(sys.stdin).get("cameras",[])
for c in cams:
    if not c.get("online"):
        print("SKIP", c.get("id"), "offline")
        continue
    cid=c["id"]
    req=urllib.request.Request(f"http://127.0.0.1:8080/api/preview/{cid}/whep/start", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body=r.read()[:300]
            print("OK", cid, c.get("link"), c.get("ip"), r.status, body)
    except Exception as e:
        err=getattr(e, "read", lambda: b"")()
        print("FAIL", cid, c.get("link"), c.get("ip"), type(e).__name__, e, err[:400])
'

echo "=== last cam logs ==="
for f in /tmp/bhvr-preview-*-cam.log; do
  [[ -f $f ]] || continue
  echo "---- $f ----"
  tail -15 "$f"
done
echo "=== remux ==="
for f in /tmp/bhvr-preview-*-remux.log; do
  [[ -f $f ]] || continue
  echo "---- $f ----"
  tail -10 "$f"
done

echo "=== kiosk log ==="
tail -50 /tmp/kiosk-web.log 2>/dev/null || true

echo "=== import check ==="
cd "$HOME/bhvr-kiosk" && .venv/bin/python -c '
from app.preview import cam_live_annexb_remote, cam_free_encode_remote, preview_settings
from app.main import load_config
cfg=load_config()
s=preview_settings(cfg)
print("transport", s.transport, "fps", s.fps_idle, "wh", s.width, s.height)
print("annexb_head", cam_live_annexb_remote(s)[:120])
'
