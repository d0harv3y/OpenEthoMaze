#!/bin/bash
# Kill fan-out workers. Do NOT pkill -f patterns that appear in parent ssh argv.
set -uo pipefail
self=$$
kill_matching() {
  local pat=$1
  ps -eo pid=,args= | while read -r pid args; do
    [[ "$pid" == "$self" ]] && continue
    [[ "$args" == *"$pat"* ]] || continue
    [[ "$args" == *"ps -eo"* ]] && continue
    [[ "$args" == *"_cleanup_fanout"* ]] && continue
    kill -9 "$pid" 2>/dev/null || true
  done
}
kill_matching "_litmus_fanout_x4.sh"
kill_matching "fanout_scale_"
kill_matching "fanout_bhvr-cam"
killall -9 ffmpeg 2>/dev/null || true
for n in 0 1 2 3; do
  fuser -k "$((16560 + n))/tcp" 2>/dev/null || true
done
sleep 1
echo "ffmpeg=$(pgrep -c ffmpeg || echo 0)"
bash "$HOME/deploy/bhvr-nvr/scripts/_ensure_mediamtx_ports.sh" || true
