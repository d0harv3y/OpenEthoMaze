#!/bin/bash
# Mode 2 Leg B only: encode baseline + mpegts.js chase/stash matrix.
# Run ON NVR after deploying kiosk with /api/diag/live-player + URL knobs.
#
#   bash _litmus_mode2_mpegts_player_knobs.sh
#
# Flow:
#   1) Ensure transport=mpegts; optional LEGS=B wall_fps/ttff via _litmus_mode2_ab_auto.sh
#   2) For each (chase, stash): wait for browser samples (hard-refresh URL), score buffered_s
#
# URL knobs (kiosk): ?chase=0|1&stash=32|64|128&paint=1
# Glass clap/LED still human — buffered_s is MSE ahead, not glass-to-glass.
#
# Env:
#   SAMPLE_S=12          encode baseline + per-rung browser sample window
#   WAIT_S=90            max wait for browser samples per rung
#   SKIP_ENCODE=0        set 1 to skip ab_auto LEGS=B
#   MATRIX=              override "0:128 0:64 0:32 1:128 1:64 1:32"
#   PAINT=1              query paint=N for all rungs
#   KIOSK_URL=http://127.0.0.1:8080
set -euo pipefail

API="${API:-http://127.0.0.1:8080}"
KIOSK="${HOME}/bhvr-kiosk"
NVR_WLAN="${NVR_WLAN:-10.248.238.22}"
SAMPLE_S="${SAMPLE_S:-12}"
WAIT_S="${WAIT_S:-90}"
SKIP_ENCODE="${SKIP_ENCODE:-0}"
PAINT="${PAINT:-1}"
KIOSK_URL="${KIOSK_URL:-http://127.0.0.1:8080}"
MATRIX="${MATRIX:-0:128 0:64 0:32 1:128 1:64 1:32}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${OUT_DIR:-/tmp}"
CSV="${OUT_DIR}/mode2_player_knobs_${STAMP}.csv"
SUM="${OUT_DIR}/mode2_player_knobs_${STAMP}.txt"
AB_AUTO="${HOME}/deploy/bhvr-nvr/scripts/_litmus_mode2_ab_auto.sh"

prog() { echo "$*" >&2; echo "$*" >>"$SUM"; }
: >"$SUM"
prog "=== Mode2 mpegts player-knob litmus $STAMP SAMPLE_S=$SAMPLE_S ==="

# Ensure mpegts + wlan nvr_host (keep buffer_count)
python3 - <<PY
from pathlib import Path
import yaml
p = Path.home() / "bhvr-kiosk" / "config.yaml"
cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
prev = dict(cfg.get("preview") or {})
prev["transport"] = "mpegts"
prev["nvr_host"] = "$NVR_WLAN"
cfg["preview"] = prev
p.write_text(yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False), encoding="utf-8")
print("transport", prev.get("transport"), "buffer_count", prev.get("buffer_count"), "nvr_host", prev.get("nvr_host"))
PY

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
  return 1
}

restart_kiosk || prog "WARN: health slow after restart"
curl -sS -m 5 "$API/api/health" | tee -a "$SUM"
echo >>"$SUM"

if [[ "$SKIP_ENCODE" != "1" && -x "$AB_AUTO" ]]; then
  prog ""
  prog "--- encode baseline LEGS=B (wall_fps / ttff) ---"
  SAMPLE_S="$SAMPLE_S" LEGS=B RESTORE=0 bash "$AB_AUTO" | tee -a "$SUM" || prog "WARN: encode baseline failed"
else
  prog "SKIP_ENCODE=1 or missing $AB_AUTO"
fi

echo "chase,stash,paint,n_samples,buffered_s_min,buffered_s_med,buffered_s_max,stream_fps_min,stream_fps_med,stream_fps_max,url,notes" >"$CSV"

prog ""
prog "--- player knob matrix (browser must hard-refresh each URL; start all 4 tiles) ---"
prog "Glass clap/LED: note stopwatch next to each rung (not auto)."

for pair in $MATRIX; do
  chase="${pair%%:*}"
  stash="${pair##*:}"
  url="${KIOSK_URL}/?chase=${chase}&stash=${stash}&paint=${PAINT}"
  prog ""
  prog ">>> RUNG chase=$chase stash=$stash paint=$PAINT"
  prog ">>> Hard-refresh kiosk: $url"
  prog ">>> Start LIVE on all online cams; wait for buf=… on badges"
  curl -sS -m 5 -X DELETE "$API/api/diag/live-player" >/dev/null || true

  # Wait until we see matching samples, then collect for SAMPLE_S
  SAMPLE_S="$SAMPLE_S" WAIT_S="$WAIT_S" API="$API" CHASE="$chase" STASH="$stash" PAINT="$PAINT" \
  python3 - <<'PY' | tee -a "$SUM"
import json, os, time, urllib.request, urllib.error

api = os.environ["API"].rstrip("/")
chase = os.environ["CHASE"] == "1"
stash = int(os.environ["STASH"])
sample_s = float(os.environ["SAMPLE_S"])
wait_s = float(os.environ["WAIT_S"])
q = f"chase={'true' if chase else 'false'}&stash={stash}&since_s=5"

def get():
    with urllib.request.urlopen(f"{api}/api/diag/live-player?{q}", timeout=8) as r:
        return json.load(r)

t0 = time.time()
armed = False
arm_t = None
last_n = 0
while time.time() - t0 < wait_s:
    try:
        j = get()
    except Exception as e:
        print(f"poll_err {e}", flush=True)
        time.sleep(1)
        continue
    n = int(j.get("n") or 0)
    if n > last_n:
        print(f"samples n={n} buffered={j.get('buffered_s')} fps={j.get('stream_fps')}", flush=True)
        last_n = n
    if n >= 2 and not armed:
        armed = True
        arm_t = time.time()
        print(f"ARMED collecting {sample_s:.0f}s…", flush=True)
    if armed and arm_t is not None and time.time() - arm_t >= sample_s:
        break
    time.sleep(1)
else:
    print("TIMEOUT waiting for browser samples", flush=True)

# Final aggregate over sample window
try:
    with urllib.request.urlopen(
        f"{api}/api/diag/live-player?chase={'true' if chase else 'false'}&stash={stash}&since_s={sample_s + 5}",
        timeout=8,
    ) as r:
        j = json.load(r)
except Exception as e:
    j = {"n": 0, "buffered_s": {"min": None, "med": None, "max": None, "n": 0},
         "stream_fps": {"min": None, "med": None, "max": None, "n": 0}, "error": str(e)}

b, f = j.get("buffered_s") or {}, j.get("stream_fps") or {}
print(
    "RESULT_RUNG "
    f"chase={int(chase)} stash={stash} n={j.get('n')} "
    f"buf_med={b.get('med')} fps_med={f.get('med')}",
    flush=True,
)
# Machine line for bash CSV
print(
    "CSV|"
    f"{int(chase)}|{stash}|{os.environ.get('PAINT', '1')}|{j.get('n')}|"
    f"{b.get('min')}|{b.get('med')}|{b.get('max')}|"
    f"{f.get('min')}|{f.get('med')}|{f.get('max')}",
    flush=True,
)
PY

  # Append CSV from last CSV| line
  line=$(grep '^CSV|' "$SUM" | tail -1 || true)
  if [[ -n "$line" ]]; then
    IFS='|' read -r _ c s p n bmin bmed bmax fmin fmed fmax <<<"$line"
    notes="stopwatch_s="
    echo "$c,$s,$p,$n,$bmin,$bmed,$bmax,$fmin,$fmed,$fmax,$url,$notes" >>"$CSV"
  else
    echo "$chase,$stash,$PAINT,0,,,,,,,,,TIMEOUT $url," >>"$CSV"
  fi
done

prog ""
prog "=== DONE ==="
prog "csv: $CSV"
prog "summary: $SUM"
prog "Lower buffered_s_med with chase=on is the objective win; clap if glass also improves."
column -t -s, "$CSV" 2>/dev/null || cat "$CSV"
echo "$CSV"
