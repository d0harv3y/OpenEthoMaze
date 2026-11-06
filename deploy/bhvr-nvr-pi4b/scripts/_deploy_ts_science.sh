#!/bin/bash
# Deploy MPEG-TS science + live byte-tee. Run ON NVR after scp to /tmp/bhvr-ts-science.
set -euxo pipefail
SRC=/tmp/bhvr-ts-science
KIOSK="${HOME}/bhvr-kiosk"
cp -f "$SRC/main.py" "$KIOSK/app/main.py"
cp -f "$SRC/preview.py" "$KIOSK/app/preview.py"
cp -f "$SRC/index.html" "$KIOSK/app/templates/index.html"
if [[ -f "$SRC/test_preview_settings.py" ]]; then
  cp -f "$SRC/test_preview_settings.py" "$KIOSK/tests/test_preview_settings.py"
fi

cd "$KIOSK"
.venv/bin/python - <<'PY'
from app.preview import cam_science_ssh_mpegts_remote, cam_live_ssh_mpegts_remote, preview_settings

s = preview_settings({"preview": {"transport": "mpegts", "buffer_count": 3}})
r = cam_live_ssh_mpegts_remote(s)
assert "mpegts" in r and "--save-pts" not in r
r2 = cam_science_ssh_mpegts_remote(
    width=1296,
    height=972,
    soft_fps=20,
    bitrate_bps=2_500_000,
    intra=20,
    sensor_mode="1296:972",
    buffer_count=6,
    pts_remote="/tmp/t.pts",
    workdir="/tmp",
)
assert "--save-pts" in r2 and "mpegts" in r2 and "-c copy" in r2
from app import main as m

src = open(m.__file__, encoding="utf-8").read()
assert "cam_science_ssh_mpegts_remote" in src
assert "_video.ts" in src
assert "nvr_ffmpeg_annex_b_to_mpegts_pipe" not in src
assert "mpegts byte-tee" in src
print("IMPORT_LITMUS_OK", m.__file__)
PY

pkill -f 'uvicorn app.main:app' 2>/dev/null || true
pkill -f 'uvicorn app.main' 2>/dev/null || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >>/tmp/kiosk-web.log 2>&1 &
disown || true
for _ in $(seq 1 20); do
  curl -sS -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break
  sleep 0.5
done
curl -sS -m 5 http://127.0.0.1:8080/api/health
echo
echo DEPLOY_TS_SCIENCE_OK
