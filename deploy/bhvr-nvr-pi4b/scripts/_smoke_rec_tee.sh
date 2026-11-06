#!/bin/bash
# Reproduce live-while-recording mpegts tee on NVR.
set -eu
BASE=http://127.0.0.1:8080

# Stop any leftover session
curl -sS -X POST "$BASE/api/session/stop" >/dev/null 2>&1 || true
sleep 1

python3 - <<'PY'
import json, urllib.request, urllib.error, time, pathlib

BASE = "http://127.0.0.1:8080"

def req(method, path, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

# Ensure idle stopped so science can take cams
req("POST", "/api/preview/stop")

code, raw = req(
    "POST",
    "/api/session/start",
    {
        "subject_id": "smoke-live-tee",
        "sex": "U",
        "profile": "lite",
        "soft_fps": 10,
        "camera_ids": ["bhvr-cam0"],
        "notes": "tee smoke",
    },
)
print("START", code, raw[:400].decode(errors="replace"))
if code >= 400:
    raise SystemExit(1)

time.sleep(3)
code, raw = req("GET", "/api/health")
print("HEALTH", raw.decode())

code, raw = req("POST", "/api/preview/bhvr-cam0/whep/start")
print("WHEP_WHILE_REC", code, raw[:240].decode(errors="replace"))

# Stream tee for a few seconds (socket timeout generous; first byte can wait for IDR)
r = urllib.request.Request(BASE + "/api/preview/bhvr-cam0?t=smoke")
try:
    with urllib.request.urlopen(r, timeout=20) as resp:
        chunks = []
        t0 = time.time()
        while time.time() - t0 < 6:
            b = resp.read(4096)
            if not b:
                break
            chunks.append(b)
            if sum(len(x) for x in chunks) > 50_000:
                break
        blob = b"".join(chunks)
        print("TEE_HTTP", resp.status, "bytes", len(blob), "ctype", resp.headers.get("Content-Type"))
        pathlib.Path("/tmp/tee_smoke.ts").write_bytes(blob[:200000])
        if len(blob) < 188:
            print("TEE_TOO_SMALL")
except urllib.error.HTTPError as e:
    print("TEE_FAIL", e.code, e.read()[:400].decode(errors="replace"))
except Exception as e:
    print("TEE_EXC", type(e).__name__, e)

log = pathlib.Path("/tmp/bhvr-preview-bhvr-cam0-rec.log")
if log.is_file():
    print("REMUX_LOG", repr(log.read_text(errors="replace")[-800:]))
else:
    print("REMUX_LOG missing")
# Capture writer / tee lines from kiosk log
try:
    lines = pathlib.Path("/tmp/kiosk-web.log").read_text(errors="replace").splitlines()[-40:]
    for ln in lines:
        if "rec-tee" in ln or "feed" in ln:
            print("KLOG", ln)
except OSError:
    pass

code, raw = req("POST", "/api/session/stop")
print("STOP", code, raw[:300].decode(errors="replace"))
PY
