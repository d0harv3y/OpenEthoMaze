#!/bin/bash
# Ensure MediaMTX listens on 15550-15553. Restart only if still missing after a short wait.
set -uo pipefail
MTX_BIN="${MTX_BIN:-$HOME/bhvr-mediamtx/mediamtx}"
MTX_CFG="${MTX_CFG:-$HOME/bhvr-mediamtx/mediamtx.yml}"

port_count() {
  local n=0 p
  # -p not required; avoids empty ss on some hosts
  for p in 15550 15551 15552 15553; do
    ss -uln 2>/dev/null | grep -q ":${p} " && n=$((n + 1))
  done
  echo "$n"
}

n=$(port_count)
if [[ "$n" -eq 4 ]] && pgrep -x mediamtx >/dev/null; then
  echo "ok already"
  ss -uln | grep -E '1555[0-3]' || true
  exit 0
fi

# Brief settle (bindings can lag right after churn)
for _ in $(seq 1 6); do
  n=$(port_count)
  [[ "$n" -eq 4 ]] && pgrep -x mediamtx >/dev/null && break
  sleep 0.4
done
n=$(port_count)
if [[ "$n" -eq 4 ]] && pgrep -x mediamtx >/dev/null; then
  echo "ok settled"
  ss -uln | grep -E '1555[0-3]' || true
  exit 0
fi

echo "missing ports=$n — restarting mediamtx"
pkill -x mediamtx 2>/dev/null || true
sleep 1
nohup "$MTX_BIN" "$MTX_CFG" >/tmp/mediamtx.log 2>&1 &
for _ in $(seq 1 20); do
  n=$(port_count)
  if [[ "$n" -eq 4 ]]; then
    echo "ok ports=$n pid=$(pgrep -x mediamtx || true)"
    ss -uln | grep -E '1555[0-3]' || true
    exit 0
  fi
  sleep 0.3
done
echo "FAIL ports after restart (have $n)"
ss -uln | grep 1555 || true
exit 1
