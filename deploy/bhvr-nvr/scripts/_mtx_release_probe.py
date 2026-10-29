#!/usr/bin/env python3
import json
import urllib.request

url = "https://api.github.com/repos/bluenviron/mediamtx/releases/latest"
with urllib.request.urlopen(url, timeout=30) as r:
    data = json.load(r)
print(data["tag_name"])
for a in data["assets"]:
    name = a["name"]
    if "linux_arm64" in name:
        print(name)
        print(a["browser_download_url"])
