#!/bin/bash
# Install MediaMTX linux_arm64 on the NVR (run ON bhvr-nvr0).
set -euo pipefail

ROOT="${HOME}/bhvr-mediamtx"
REPO_YML="$(dirname "$0")/../mediamtx/mediamtx.yml"
UNIT_SRC="$(dirname "$0")/../systemd/bhvr-mediamtx.service"
TAG="${MEDIAMTX_TAG:-}"

mkdir -p "$ROOT"
cd /tmp

if [[ -z "$TAG" ]]; then
  TAG=$(python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen(
    "https://api.github.com/repos/bluenviron/mediamtx/releases/latest", timeout=60
) as r:
    print(json.load(r)["tag_name"])
PY
)
fi
echo "tag=$TAG"

ASSET="mediamtx_${TAG}_linux_arm64.tar.gz"
URL="https://github.com/bluenviron/mediamtx/releases/download/${TAG}/${ASSET}"
curl -fL --retry 3 -o "/tmp/${ASSET}" "$URL"
tar -C "$ROOT" -xzf "/tmp/${ASSET}"
test -x "$ROOT/mediamtx"
"$ROOT/mediamtx" --version || "$ROOT/mediamtx" -h | head -3 || true
echo "$TAG" >"$ROOT/VERSION"

# Config: prefer repo copy if present next to this script, else keep existing.
if [[ -f "$REPO_YML" ]]; then
  sed 's/\r$//' "$REPO_YML" >"$ROOT/mediamtx.yml"
elif [[ ! -f "$ROOT/mediamtx.yml" ]]; then
  echo "missing mediamtx.yml" >&2
  exit 1
fi

# Inject live IPs into webrtcAdditionalHosts.
python3 - <<'PY'
from pathlib import Path
import re
import subprocess

yml = Path.home() / "bhvr-mediamtx" / "mediamtx.yml"
text = yml.read_text(encoding="utf-8")
hosts = ["127.0.0.1", "192.168.7.1"]
try:
    out = subprocess.check_output(
        ["ip", "-4", "-br", "addr", "show", "wlan0"], text=True
    )
    # wlan0 UP 10.248.238.22/20
    m = re.search(r"(\d+\.\d+\.\d+\.\d+)", out)
    if m and m.group(1) not in hosts:
        hosts.append(m.group(1))
except Exception:
    pass
line = "webrtcAdditionalHosts: [" + ", ".join(hosts) + "]"
text2, n = re.subn(
    r"^webrtcAdditionalHosts:.*$", line, text, count=1, flags=re.M
)
if n != 1:
    raise SystemExit("webrtcAdditionalHosts line missing in mediamtx.yml")
yml.write_text(text2, encoding="utf-8")
print(line)
PY

if [[ -f "$UNIT_SRC" ]]; then
  UNIT_DST=/etc/systemd/system/bhvr-mediamtx.service
  if sudo -n true 2>/dev/null; then
    sed 's/\r$//' "$UNIT_SRC" | sudo tee "$UNIT_DST" >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable bhvr-mediamtx.service
    sudo systemctl restart bhvr-mediamtx.service
    sleep 1
    systemctl --no-pager --full status bhvr-mediamtx.service | head -20
  else
    echo "NOTE: passwordless sudo unavailable — unit at $UNIT_SRC"
    echo "  sudo cp $UNIT_SRC $UNIT_DST && sudo systemctl enable --now bhvr-mediamtx"
    echo "  (or run: nohup $ROOT/mediamtx $ROOT/mediamtx.yml >/tmp/mediamtx.log 2>&1 &)"
  fi
else
  echo "unit source missing — binary installed at $ROOT; start manually" >&2
fi

echo "OK $ROOT tag=$TAG"
