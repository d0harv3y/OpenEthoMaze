#!/bin/bash
# Stop native mpv 2×2 spike windows (does not stop MediaMTX / kiosk publishers).
set -euo pipefail
PIDDIR="${PIDDIR:-/tmp/bhvr-mpv-grid}"
echo "=== stop mpv grid ==="
if [[ -d "$PIDDIR" ]]; then
  for f in "$PIDDIR"/*.pid; do
    [[ -f "$f" ]] || continue
    pid=$(cat "$f" 2>/dev/null || true)
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "killed $pid ($(basename "$f" .pid))"
    fi
    rm -f "$f"
  done
fi
pkill -f "mpv.*bhvr-mpv-grid" 2>/dev/null || true
echo "done (publishers left running — POST /api/preview/stop if you want those off too)"
