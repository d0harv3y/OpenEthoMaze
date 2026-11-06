#!/bin/bash
set -euxo pipefail
cp -f /tmp/preview.py "$HOME/bhvr-kiosk/app/preview.py" 2>/dev/null || true
cd "$HOME/bhvr-kiosk"
.venv/bin/python <<'PY'
import subprocess, time, yaml
from pathlib import Path
import sys
sys.path.insert(0, str(Path.home() / "bhvr-kiosk"))
from app.preview import preview_settings, cam_live_ssh_mpegts_remote

cfg = yaml.safe_load((Path.home() / "bhvr-kiosk" / "config.yaml").read_text()) or {}
host = "10.248.229.141"
user = cfg.get("ssh_user", "admin")
ident = cfg.get("ssh_identity_file", str(Path.home() / ".ssh" / "id_ed25519_bhvr"))
s = preview_settings(cfg)
remote = cam_live_ssh_mpegts_remote(s)
print("REMOTE_HAS_BIN", "bin/ffmpeg" in remote)
print("REMOTE_HEAD", remote[:220])
argv = [
    "ssh", "-i", ident, "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=5",
    f"{user}@{host}", remote,
]
err = open("/tmp/probe_mpegts_ssh.err", "wb")
p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=err, stdin=subprocess.DEVNULL, bufsize=0)
assert p.stdout
n = 0
t0 = time.time()
while time.time() - t0 < 12:
    chunk = p.stdout.read(4096)
    if not chunk:
        print("EOF at", round(time.time()-t0, 2), "total", n)
        break
    n += len(chunk)
    print("got", len(chunk), "total", n, "t", round(time.time()-t0, 2))
    if n >= 60000:
        break
print("TOTAL", n, "elapsed", round(time.time() - t0, 2), "rc", p.poll())
p.terminate()
try:
    p.wait(timeout=3)
except Exception:
    p.kill()
err.close()
print("ERR_TAIL:")
print(Path("/tmp/probe_mpegts_ssh.err").read_text(errors="replace")[-800:])
PY
