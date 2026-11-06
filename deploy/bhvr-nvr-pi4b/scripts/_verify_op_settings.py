#!/usr/bin/env python3
import json
import urllib.request
from pathlib import Path

with urllib.request.urlopen("http://127.0.0.1:8080/api/operator/settings", timeout=5) as r:
    data = json.loads(r.read().decode("utf-8"))
s = data["settings"]
print("h5_pack", s.get("h5_pack"), "tag", repr(s.get("recording_tag")))
print("keys_ok", "h5_pack" in s, "recording_tag" in s)
html = Path.home() / "bhvr-kiosk/app/templates/index.html"
text = html.read_text(encoding="utf-8")
print("ui_h5", "pack TS into H5" in text)
print("ui_tag", 'id="recording_tag"' in text)
print("ui_default_ses", 'placeholder="ses"' in text)
