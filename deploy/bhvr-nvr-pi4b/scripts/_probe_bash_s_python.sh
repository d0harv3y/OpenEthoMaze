#!/bin/bash
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
IP=10.248.233.15
SCRIPT=$(.venv/bin/python -c 'from app.preview import cam_live_ssh_mpegts_remote, preview_settings; print(cam_live_ssh_mpegts_remote(preview_settings({"preview":{"transport":"mpegts","buffer_count":3}})))')

echo "=== printf|ssh bash -s (8s) ==="
rm -f /tmp/pipe_printf.ts
printf '%s\n' "$SCRIPT" | ssh "${KEY[@]}" "admin@$IP" bash -s > /tmp/pipe_printf.ts 2>/tmp/pipe_printf.err &
pid=$!
sleep 8
kill "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true
wc -c /tmp/pipe_printf.ts
tail -3 /tmp/pipe_printf.err || true

echo "=== python _popen_ssh_bash_s ==="
.venv/bin/python - <<'PY'
import time
from pathlib import Path
from app.main import _popen_ssh_bash_s, load_config
from app.preview import cam_live_ssh_mpegts_remote, preview_settings

cfg = load_config()
script = cam_live_ssh_mpegts_remote(preview_settings(cfg))
err = open("/tmp/pipe_py.err", "wb")
proc = _popen_ssh_bash_s(cfg, "10.248.233.15", script, err_f=err)
out = open("/tmp/pipe_py.ts", "wb")
t0 = time.time()
n = 0
assert proc.stdout is not None
while time.time() - t0 < 8:
    chunk = proc.stdout.read(65536)
    if not chunk:
        break
    out.write(chunk)
    n += len(chunk)
proc.kill()
out.close()
err.close()
print("bytes", n, "file", Path("/tmp/pipe_py.ts").stat().st_size)
print(Path("/tmp/pipe_py.err").read_text(errors="replace")[-400:])
PY
