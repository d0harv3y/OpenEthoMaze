#!/bin/bash
# Mode 2 A/B auto litmus (objective side). Run ON NVR.
#
#   bash _litmus_mode2_ab_auto.sh
#
# mpegts.js chase/stash matrix (Leg B + browser buffered_s):
#   bash _litmus_mode2_mpegts_player_knobs.sh
#
# Flips Leg A (whep + nvr_annexb → MediaMTX RTSP/WHEP) then Leg B
# (SSH MPEG-TS → HTTP /api/preview). For each online WLAN cam:
#   - start_ms / ttff_ms (path-specific readiness proxies)
#   - wall_fps over SAMPLE_S (ffmpeg -c copy frame count / wall)
# Writes CSV + summary under /tmp. Restores prior config.yaml at end.
#
# Does NOT measure glass-to-glass (clap/LED still human).
#
# Env:
#   SAMPLE_S=15          measure window per cam (default 15)
#   BUFFER_COUNT=        optional override; else keep yaml value
#   NVR_WLAN=10.248.238.22
#   LEGS=A,B             which legs to run
#   RESTORE=1            restore config after (default 1)
set -euo pipefail

API="${API:-http://127.0.0.1:8080}"
KIOSK="${HOME}/bhvr-kiosk"
NVR_WLAN="${NVR_WLAN:-10.248.238.22}"
SAMPLE_S="${SAMPLE_S:-15}"
LEGS="${LEGS:-A,B}"
RESTORE="${RESTORE:-1}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${OUT_DIR:-/tmp}"
CSV="${OUT_DIR}/mode2_ab_${STAMP}.csv"
SUM="${OUT_DIR}/mode2_ab_${STAMP}.txt"
CFG_BAK="${OUT_DIR}/mode2_ab_${STAMP}_config.bak.yaml"

prog() { echo "$*" >&2; echo "$*" >>"$SUM"; }
: >"$SUM"

cp -a "$KIOSK/config.yaml" "$CFG_BAK"
prog "=== Mode2 A/B auto $STAMP SAMPLE_S=$SAMPLE_S LEGS=$LEGS ==="
prog "config backup: $CFG_BAK"

restart_kiosk() {
  pids=$(pgrep -f '[u]vicorn app.main' || true)
  if [[ -n "${pids}" ]]; then kill -9 $pids || true; fi
  sleep 1
  cd "$KIOSK"
  nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
    >>/tmp/kiosk-web.log 2>&1 &
  disown || true
  for _ in $(seq 1 20); do
    curl -sS -m 2 "$API/api/health" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  prog "WARN: health not ready after restart"
  return 1
}

patch_leg() {
  local leg="$1"
  BUFFER_COUNT="${BUFFER_COUNT:-}" NVR_WLAN="$NVR_WLAN" LEG="$leg" python3 - <<'PY'
import os
from pathlib import Path
import yaml

p = Path.home() / "bhvr-kiosk" / "config.yaml"
cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
prev = dict(cfg.get("preview") or {})
prev["nvr_host"] = os.environ["NVR_WLAN"]
buf = os.environ.get("BUFFER_COUNT", "").strip()
if buf:
    prev["buffer_count"] = max(1, int(buf))
leg = os.environ["LEG"]
if leg == "A":
    prev["transport"] = "whep"
    prev["whep_ingest"] = "nvr_annexb"
else:
    prev["transport"] = "mpegts"
cfg["preview"] = prev
p.write_text(yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False), encoding="utf-8")
print(
    "patched leg=%s transport=%s whep_ingest=%s buffer_count=%s nvr_host=%s"
    % (
        leg,
        prev.get("transport"),
        prev.get("whep_ingest"),
        prev.get("buffer_count"),
        prev.get("nvr_host"),
    )
)
PY
}

online_cams() {
  python3 - <<'PY'
import json, subprocess, urllib.request
key = [
    "ssh",
    "-i", __import__("os").path.expanduser("~/.ssh/id_ed25519_bhvr"),
    "-o", "IdentitiesOnly=yes",
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=6",
    "-o", "StrictHostKeyChecking=accept-new",
]
cams = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/cams", timeout=8))["cameras"]
rows = []
for c in sorted(cams, key=lambda x: x.get("id") or ""):
    if not c.get("online"):
        continue
    ip = str(c.get("ip") or "")
    if not ip or ip.startswith("192.168.7."):
        continue
    try:
        subprocess.check_call(
            key + [f"admin@{ip}", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        continue
    rows.append(f"{c['id']}\t{ip}")
if not rows:
    raise SystemExit("no online WLAN cams with SSH")
print("\n".join(rows))
PY
}

measure_leg() {
  local leg="$1"
  SAMPLE_S="$SAMPLE_S" API="$API" LEG="$leg" CSV="$CSV" python3 - <<'PY'
import csv
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

api = os.environ["API"].rstrip("/")
leg = os.environ["LEG"]
sample_s = float(os.environ["SAMPLE_S"])
csv_path = Path(os.environ["CSV"])
cams = []
for ln in Path("/tmp/mode2_ab_cams.tsv").read_text(encoding="utf-8").splitlines():
    parts = ln.split("\t")
    if len(parts) >= 2:
        cams.append((parts[0], parts[1]))

fields = [
    "stamp", "leg", "cam_id", "ip", "ok", "start_ms", "ttff_ms",
    "wall_fps", "frames", "sample_s", "bytes", "whep_options", "notes",
]
stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
write_header = not csv_path.exists()
lock = threading.Lock()
rows = []


def parse_ffmpeg_wall(log_text: str, dur: float):
    fr = re.findall(r"frame=\s*(\d+)", log_text)
    fps_tail = re.findall(r"fps=\s*([0-9.]+)", log_text)
    if not fr:
        return None, 0, fps_tail[-3:] if fps_tail else []
    frames = int(fr[-1])
    wall = frames / dur if dur > 0 else None
    return wall, frames, fps_tail[-3:] if fps_tail else []


def rtsp_ready(cam_id: str, timeout_s: float = 12.0):
    """Poll until RTSP DESCRIBE works; return ms wait or None."""
    t0 = time.perf_counter()
    url = f"rtsp://127.0.0.1:8554/{cam_id}"
    while time.perf_counter() - t0 < timeout_s:
        try:
            r = subprocess.run(
                [
                    "timeout", "3",
                    "ffprobe", "-v", "error", "-rtsp_transport", "tcp",
                    "-show_entries", "stream=codec_type", "-of", "csv=p=0", url,
                ],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and "video" in (r.stdout or "").lower():
                return (time.perf_counter() - t0) * 1000.0
        except subprocess.TimeoutExpired:
            pass
        time.sleep(0.5)
    return None


def ffmpeg_rtsp_wall(cam_id: str, dur: float):
    clog = Path(f"/tmp/mode2_ab_a_{cam_id}.log")
    cmd = [
        "timeout", str(int(dur) + 3),
        "ffmpeg", "-hide_banner", "-loglevel", "info",
        "-rtsp_transport", "tcp",
        "-i", f"rtsp://127.0.0.1:8554/{cam_id}",
        "-c", "copy", "-f", "null", "-",
    ]
    with open(clog, "wb") as err:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=err, check=False)
    text = clog.read_text(errors="replace")
    return parse_ffmpeg_wall(text, dur), text[-300:]


def whep_start(cam_id: str):
    t0 = time.perf_counter()
    req = urllib.request.Request(f"{api}/api/preview/{cam_id}/whep/start", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode(errors="replace")[:180]
            ms = (time.perf_counter() - t0) * 1000.0
            return True, ms, resp.status, body
    except urllib.error.HTTPError as e:
        ms = (time.perf_counter() - t0) * 1000.0
        err = e.read().decode(errors="replace")[:160]
        return False, ms, e.code, err
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000.0
        return False, ms, 0, str(e)


def whep_options_code(cam_id: str) -> str:
    try:
        opt = urllib.request.Request(
            f"http://127.0.0.1:8889/{cam_id}/whep", method="OPTIONS"
        )
        with urllib.request.urlopen(opt, timeout=3) as resp:
            return str(resp.status)
    except Exception:
        return ""


def measure_mpegts_to_file(cam_id: str, dur: float):
    """Pull HTTP MPEG-TS for dur seconds; TTFF = first 188 bytes."""
    url = f"{api}/api/preview/{cam_id}?t=mode2ab-{int(time.time()*1000)}"
    dest = Path(f"/tmp/mode2_ab_b_{cam_id}.ts")
    if dest.exists():
        dest.unlink()
    notes = []
    t0 = time.perf_counter()
    start_ms = None
    ttff_ms = None
    nbytes = 0
    try:
        resp = urllib.request.urlopen(url, timeout=90)
        start_ms = (time.perf_counter() - t0) * 1000.0
        deadline_payload = None
        with dest.open("wb") as out:
            while True:
                chunk = resp.read(65536)
                now = time.perf_counter()
                if not chunk:
                    notes.append("eof")
                    break
                out.write(chunk)
                nbytes += len(chunk)
                if ttff_ms is None and nbytes >= 188:
                    ttff_ms = (now - t0) * 1000.0
                    deadline_payload = now + dur
                if deadline_payload is not None and now >= deadline_payload:
                    break
                if now - t0 > dur + 30:
                    notes.append("cap")
                    break
        try:
            resp.close()
        except Exception:
            pass
    except Exception as e:
        return {
            "ok": 0, "start_ms": round(start_ms, 1) if start_ms is not None else "",
            "ttff_ms": round(ttff_ms, 1) if ttff_ms is not None else "",
            "wall_fps": "", "frames": 0, "bytes": nbytes, "whep_options": "",
            "notes": f"pull_fail {e}; " + ";".join(notes),
        }

    if ttff_ms is None:
        return {
            "ok": 0, "start_ms": round(start_ms, 1) if start_ms is not None else "",
            "ttff_ms": "", "wall_fps": "", "frames": 0, "bytes": nbytes,
            "whep_options": "", "notes": "no_ttff; " + ";".join(notes),
        }

    clog = Path(f"/tmp/mode2_ab_b_{cam_id}.log")
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "info",
        "-probesize", "2000000", "-analyzeduration", "2000000",
        "-f", "mpegts", "-i", str(dest),
        "-c", "copy", "-f", "null", "-",
    ]
    with open(clog, "wb") as err:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=err, check=False)
    log_text = clog.read_text(errors="replace")
    # Use file duration from ffprobe if available; else sample_s
    wall, frames, fps_tail = parse_ffmpeg_wall(log_text, dur)
    # Prefer wall from frames / actual pull duration after ttff
    pull_payload_s = max(0.001, (time.perf_counter() - t0) - ttff_ms / 1000.0)
    # Recompute using recorded file via ffprobe packet count if frame= missing
    if wall is None:
        pr = subprocess.run(
            [
                "ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0",
                "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(dest),
            ],
            capture_output=True, text=True, timeout=60,
        )
        pk = (pr.stdout or "").strip().split("\n")[0].strip()
        if pk.isdigit() and int(pk) > 0:
            frames = int(pk)
            # nb_read_packets ≈ frames for annex-B in TS; wall vs sample window
            wall = frames / dur
            notes.append(f"ffprobe_packets={frames}")
    if fps_tail:
        notes.append(f"fps_tail={fps_tail}")
    notes.append(f"pull_s={pull_payload_s:.1f}")
    ok = 1 if wall is not None and wall > 0 else 0
    if not ok:
        notes.append(log_text[-180:].replace("\n", " "))
    return {
        "ok": ok,
        "start_ms": round(start_ms, 1),
        "ttff_ms": round(ttff_ms, 1),
        "wall_fps": round(wall, 2) if wall is not None else "",
        "frames": frames,
        "bytes": nbytes,
        "whep_options": "",
        "notes": "; ".join(notes)[:280],
    }


def emit(cam_id, ip, m):
    row = {
        "stamp": stamp, "leg": leg, "cam_id": cam_id, "ip": ip,
        "ok": m["ok"], "start_ms": m["start_ms"], "ttff_ms": m["ttff_ms"],
        "wall_fps": m["wall_fps"], "frames": m["frames"], "sample_s": sample_s,
        "bytes": m.get("bytes", ""), "whep_options": m.get("whep_options", ""),
        "notes": m.get("notes", ""),
    }
    with lock:
        rows.append(row)
        print(
            f"leg={leg} {cam_id} ok={row['ok']} start_ms={row['start_ms']} "
            f"ttff_ms={row['ttff_ms']} wall_fps={row['wall_fps']} "
            f"frames={row['frames']} bytes={row['bytes']}",
            flush=True,
        )


if leg == "A":
    # 1) Start all cams (serial — less SSH/remux race than 4× parallel start)
    starts = {}
    for cam_id, ip in cams:
        ok, ms, code, body = whep_start(cam_id)
        starts[cam_id] = (ok, ms, code, body)
        print(f"start {cam_id} ok={ok} start_ms={ms:.1f} http={code}", flush=True)
        if not ok:
            emit(cam_id, ip, {
                "ok": 0, "start_ms": round(ms, 1), "ttff_ms": "",
                "wall_fps": "", "frames": 0, "bytes": "",
                "whep_options": "", "notes": f"whep_start_fail {code} {body}",
            })
    time.sleep(3.0)

    # 2) Serial RTSP probe+wall (parallel ffprobe hangs MediaMTX on this box)
    for cam_id, ip in cams:
        ok, ms, code, body = starts[cam_id]
        if not ok:
            continue
        notes = [body.replace("\n", " ")[:100]]
        opt = whep_options_code(cam_id)
        ready_ms = rtsp_ready(cam_id, timeout_s=15.0)
        if ready_ms is None:
            emit(cam_id, ip, {
                "ok": 0, "start_ms": round(ms, 1), "ttff_ms": "",
                "wall_fps": "", "frames": 0, "bytes": "",
                "whep_options": opt,
                "notes": "rtsp_not_ready; " + "; ".join(notes),
            })
            continue
        (wall, frames, fps_tail), tail = ffmpeg_rtsp_wall(cam_id, sample_s)
        if fps_tail:
            notes.append(f"fps_tail={fps_tail}")
        if wall is None:
            notes.append(tail.replace("\n", " "))
        emit(cam_id, ip, {
            "ok": 1 if wall else 0,
            "start_ms": round(ms, 1),
            "ttff_ms": round(ready_ms, 1),
            "wall_fps": round(wall, 2) if wall else "",
            "frames": frames,
            "bytes": "",
            "whep_options": opt,
            "notes": "; ".join(notes)[:280],
        })
else:
    # Leg B: parallel HTTP pulls (real ×N contention)
    def run_b(cam_id, ip):
        emit(cam_id, ip, measure_mpegts_to_file(cam_id, sample_s))

    threads = [
        threading.Thread(target=run_b, args=(cid, ip), daemon=True)
        for cid, ip in cams
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=sample_s + 120)

rows.sort(key=lambda r: r["cam_id"])
with csv_path.open("a", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    if write_header:
        w.writeheader()
    for r in rows:
        w.writerow(r)

fps_vals = [float(r["wall_fps"]) for r in rows if r["wall_fps"] != ""]
ttff_vals = [float(r["ttff_ms"]) for r in rows if r["ttff_ms"] != ""]
ok_n = sum(1 for r in rows if int(r["ok"]) == 1)
if fps_vals and ttff_vals:
    print(
        f"SUMMARY_LEG_{leg} n={len(rows)} ok={ok_n} "
        f"wall_fps_min={min(fps_vals):.2f} "
        f"wall_fps_med={sorted(fps_vals)[len(fps_vals)//2]:.2f} "
        f"wall_fps_max={max(fps_vals):.2f} "
        f"ttff_ms_min={min(ttff_vals):.0f} "
        f"ttff_ms_med={sorted(ttff_vals)[len(ttff_vals)//2]:.0f} "
        f"ttff_ms_max={max(ttff_vals):.0f}",
        flush=True,
    )
else:
    print(f"SUMMARY_LEG_{leg} n={len(rows)} ok={ok_n} (incomplete metrics)", flush=True)
PY
}

# --- run ---
IFS=',' read -r -a LEG_ARR <<< "$LEGS"
for leg in "${LEG_ARR[@]}"; do
  leg=$(echo "$leg" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')
  [[ "$leg" == "A" || "$leg" == "B" ]] || { prog "skip unknown leg=$leg"; continue; }
  prog ""
  prog "--- LEG $leg $(date -Is) ---"
  patch_leg "$leg" | tee -a "$SUM"
  restart_kiosk || true
  curl -sS -m 5 -X POST "$API/api/preview/stop" >/dev/null || true
  sleep 1
  online_cams | tee /tmp/mode2_ab_cams.tsv | tee -a "$SUM"
  prog "measuring ${SAMPLE_S}s × $(wc -l </tmp/mode2_ab_cams.tsv) cams…"
  set +e
  measure_leg "$leg" 2>&1 | tee -a "$SUM"
  set -e
  curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
  sleep 1
done

if [[ "$RESTORE" == "1" ]]; then
  prog ""
  prog "=== restore config from $CFG_BAK ==="
  cp -a "$CFG_BAK" "$KIOSK/config.yaml"
  restart_kiosk || true
  grep -E 'transport:|buffer_count:|nvr_host:|whep_ingest:' "$KIOSK/config.yaml" | tee -a "$SUM" || true
fi

prog ""
prog "=== DONE ==="
prog "csv: $CSV"
prog "summary: $SUM"
prog "NOTE: Leg A ttff_ms = RTSP ready after settle; Leg B ttff_ms = first ≥188 B on HTTP MPEG-TS. Neither is glass-to-glass."
echo "$CSV"
