#!/bin/bash
# BUF=N bash _set_buffer_count.sh
set -euxo pipefail
BUF="${BUF:?set BUF=}"
python3 - <<PY
from pathlib import Path
import yaml
p = Path.home() / "bhvr-kiosk" / "config.yaml"
cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
prev = cfg.get("preview") or {}
prev["buffer_count"] = int("$BUF")
prev["transport"] = prev.get("transport") or "mpegts"
cfg["preview"] = prev
p.write_text(yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False), encoding="utf-8")
print("yaml buffer_count", prev["buffer_count"])
PY
cd "$HOME/bhvr-kiosk"
.venv/bin/python - <<PY
import yaml
from pathlib import Path
from app.preview import preview_settings
cfg = yaml.safe_load(Path("config.yaml").read_text()) or {}
s = preview_settings(cfg)
print("effective", s.buffer_count)
assert s.buffer_count == int("$BUF"), s.buffer_count
PY
pids=$(pgrep -f '[u]vicorn app.main' || true)
[[ -n "$pids" ]] && kill -9 $pids || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >>/tmp/kiosk-web.log 2>&1 &
sleep 3
curl -sS -X POST http://127.0.0.1:8080/api/preview/stop >/dev/null || true
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8)
ssh "${KEY[@]}" admin@10.248.229.141 'pkill -9 rpicam-vid 2>/dev/null || true; pkill -9 -f "[f]fmpeg" 2>/dev/null || true' || true
curl -sS http://127.0.0.1:8080/api/health; echo
echo "READY_BUF${BUF}"
