"""Set operator defaults to Lite @ 30; preserve cameras / output_subdir."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

cfg_path = Path.home() / "bhvr-kiosk" / "config.yaml"
cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.is_file() else {}
root = Path((cfg or {}).get("data_root", "/data/bhvr"))
p = root / ".kiosk_operator.json"
st = {
    "profile": "lite",
    "soft_fps": 30,
    "output_subdir": "",
    "chunk_minutes": 20,
    "cameras": {},
}
if p.is_file():
    try:
        old = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(old.get("cameras"), dict):
            st["cameras"] = old["cameras"]
        st["output_subdir"] = str(old.get("output_subdir") or "")
    except (OSError, json.JSONDecodeError):
        pass
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
print("wrote", p)
print(st["profile"], st["soft_fps"], "chunk", st["chunk_minutes"])
