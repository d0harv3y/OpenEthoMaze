#!/bin/bash
set -uo pipefail
python3 - <<'PY'
import yaml
from pathlib import Path
p = Path.home() / "bhvr-kiosk" / "config.yaml"
c = yaml.safe_load(p.read_text()) or {}
prev = dict(c.get("preview") or {})
prev["buffer_count"] = 1
c["preview"] = prev
p.write_text(yaml.dump(c, default_flow_style=False, sort_keys=False))
print(prev)
PY
bash /tmp/_restart_kiosk.sh
curl -s --max-time 3 http://127.0.0.1:8080/api/health
echo
