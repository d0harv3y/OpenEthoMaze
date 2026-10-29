#!/bin/bash
# Long ladder: ×4 fan-out live ask vs science soft-30 (decoupled).
# Each rung: LIVE_WxH@FPS — science must PASS (>=25); live wall_fps vs ask.
# Progress on stderr every rung. Summary: /tmp/fanout_live_ladder.txt
set -euo pipefail

LITMUS="${HOME}/deploy/bhvr-nvr/scripts/_litmus_fanout_x4.sh"
OUT=/tmp/fanout_live_ladder.txt
: >"$OUT"
log() { echo "$*" | tee -a "$OUT"; }
prog() { echo "$*" >&2; echo "$*" >>"$OUT"; }

# Ascending live ask (WxH@fps). PASS_LIVE ≈ 75% of ask (honest tile budget).
# Format: W H FPS PASS_LIVE
RUNGS=(
  "320 180 5 4"
  "320 180 10 7"
  "480 270 5 4"
  "480 270 8 6"
  "480 270 15 10"
  "640 360 8 6"
  "640 360 15 10"
  "960 540 10 7"
  "1280 720 10 7"
)

bash "${HOME}/deploy/bhvr-nvr/scripts/_cleanup_fanout.sh" >/dev/null 2>&1 || true
bash "${HOME}/deploy/bhvr-nvr/scripts/_ensure_mediamtx_ports.sh" | tee -a "$OUT" || true

n_rungs=${#RUNGS[@]}
prog "=== live ladder start $(date -Is) rungs=$n_rungs (NVR=$(nproc)c) ==="

i=0
for rung in "${RUNGS[@]}"; do
  i=$((i + 1))
  read -r LIVE_W LIVE_H LIVE_FPS PASS_LIVE <<<"$rung"
  ask="${LIVE_W}x${LIVE_H}@${LIVE_FPS}"
  prog ""
  prog "--- rung $i/$n_rungs ask=$ask PASS_LIVE>=$PASS_LIVE $(date -Is) ---"

  bash "${HOME}/deploy/bhvr-nvr/scripts/_cleanup_fanout.sh" >/dev/null 2>&1 || true
  rm -f /tmp/fanout_bhvr-cam*.pts /tmp/fanout_bhvr-cam*_science.h264
  bash "${HOME}/deploy/bhvr-nvr/scripts/_ensure_mediamtx_ports.sh" >/dev/null 2>&1 || true

  # Shorter probe than default litmus; science still full encode until stop.
  set +e
  LIVE_W="$LIVE_W" LIVE_H="$LIVE_H" LIVE_FPS="$LIVE_FPS" \
    PASS_LIVE="$PASS_LIVE" PASS_SCI=25 DURATION_S=6 \
    bash "$LITMUS" >"/tmp/fanout_ladder_rung_${i}.log" 2>&1
  ec=$?
  set -e

  summ=$(cat /tmp/fanout_x4_summary.txt 2>/dev/null || true)
  echo "$summ" >>"$OUT"

  # Aggregate science / live from summary lines
  sci_pass=$(echo "$summ" | grep -c 'RESULT_SCIENCE .* PASS' || true)
  sci_fail=$(echo "$summ" | grep -c 'RESULT_SCIENCE .* FAIL' || true)
  live_lines=$(echo "$summ" | grep -E '^live bhvr-cam' || true)
  live_pass=$(echo "$live_lines" | grep -c ' PASS' || true)
  live_below=$(echo "$live_lines" | grep -c ' BELOW' || true)
  live_fail=$(echo "$live_lines" | grep -c ' FAIL' || true)

  # min wall_fps among measured live lines
  min_wall=$(printf '%s\n' "$live_lines" | python3 -c '
import re, sys
vals = []
for ln in sys.stdin:
    m = re.search(r"wall_fps=([0-9.]+)", ln)
    if m:
        vals.append(float(m.group(1)))
print(f"{min(vals):.2f}" if vals else "na")
')

  verdict="SOFT"
  if [[ "$sci_fail" -eq 0 && "$sci_pass" -ge 3 && "$live_pass" -ge 3 && "$live_fail" -eq 0 ]]; then
    verdict="GREEN"
  elif [[ "$sci_fail" -gt 0 ]]; then
    verdict="SCIENCE_HURT"
  elif [[ "$live_fail" -gt 0 || "$live_pass" -lt 2 ]]; then
    verdict="LIVE_DEAD"
  else
    verdict="LIVE_THIN"
  fi

  prog "RESULT rung=$i ask=$ask sci_pass=$sci_pass sci_fail=$sci_fail live_pass=$live_pass live_below=$live_below live_fail=$live_fail min_wall=$min_wall verdict=$verdict ec=$ec"
  # Stop climbing if science breaks (should not with decoupled path)
  if [[ "$verdict" == "SCIENCE_HURT" ]]; then
    prog "STOP: science compromised at ask=$ask"
    break
  fi
done

bash "${HOME}/deploy/bhvr-nvr/scripts/_cleanup_fanout.sh" >/dev/null 2>&1 || true
prog "=== live ladder DONE $(date -Is) ==="
prog "summary: $OUT"
echo "$OUT"
