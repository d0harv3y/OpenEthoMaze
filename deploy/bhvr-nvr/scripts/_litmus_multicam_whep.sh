#!/bin/bash
# Litmus: ≥2 concurrent WHEP publishers on ordinal ports (issue 12).
set -euo pipefail
API=http://127.0.0.1:8080
MTX=http://127.0.0.1:8889

curl -sS -m 10 -X POST "$API/api/preview/stop" >/dev/null || true
sleep 1

declare -a CAMS=(bhvr-cam0 bhvr-cam1)
declare -A EXPECT=([bhvr-cam0]=15550 [bhvr-cam1]=15551)

for c in "${CAMS[@]}"; do
  echo "=== start $c ==="
  out=$(curl -sS -m 60 -X POST "$API/api/preview/$c/whep/start")
  echo "$out"
  port=$(python3 -c "import json,sys; print(json.load(sys.stdin)['udp_port'])" <<<"$out")
  want=${EXPECT[$c]}
  if [[ "$port" != "$want" ]]; then
    echo "FAIL: $c port=$port want=$want" >&2
    exit 1
  fi
done

sleep 3
echo "=== health ==="
curl -sS -m 5 "$API/api/health"
echo
echo "=== whep OPTIONS ==="
for c in "${CAMS[@]}"; do
  code=$(curl -sS -m 5 -o /dev/null -w "%{http_code}" -X OPTIONS "$MTX/$c/whep")
  echo "$c options=$code"
done
echo "=== listen ports ==="
ss -ulnp | grep -E "1555[01]" || true
echo "=== cam logs (tail) ==="
for c in "${CAMS[@]}"; do
  echo "-- $c --"
  tail -8 "/tmp/bhvr-preview-${c}-cam.log" 2>/dev/null || echo "(no log)"
done
echo "=== idle list ==="
python3 - <<'PY'
import json, urllib.request
h = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/health", timeout=5))
idle = h.get("preview_idle") or []
print("preview_idle", idle)
ok = set(idle) >= {"bhvr-cam0", "bhvr-cam1"}
raise SystemExit(0 if ok else 2)
PY
