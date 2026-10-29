#!/usr/bin/env python3
"""Patch NVR kiosk config for wireless soak (no SSD required)."""
from pathlib import Path
import re

import os

cfg = Path.home() / "bhvr-kiosk" / "config.yaml"
text = cfg.read_text(encoding="utf-8")
ssd = "/media/admin/random"
# Empty mountpoint dir exists even when unmounted — require a real mount.
root = "/media/admin/random/bhvr" if os.path.ismount(ssd) else "/data/bhvr"
Path(root).mkdir(parents=True, exist_ok=True)
text = re.sub(r"^data_root:.*$", f"data_root: {root}", text, count=1, flags=re.M)
cfg.write_text(text, encoding="utf-8")
print(f"data_root={root}")
print("restart: sudo systemctl restart bhvr-kiosk-web")
