#!/bin/bash
set -uo pipefail
for c in bhvr-cam0 bhvr-cam1 bhvr-cam2 bhvr-cam3; do
  pts=/tmp/fanout_${c}.pts
  h264=/tmp/fanout_${c}_science.h264
  echo "=== $c ==="
  wc -c "$h264" 2>/dev/null || echo "no h264"
  if [[ -f "$pts" ]]; then
    wc -l "$pts"
    head -3 "$pts"
    tail -3 "$pts"
    python3 - "$pts" <<'PY'
import sys
from pathlib import Path
vals=[]
for ln in Path(sys.argv[1]).read_text().splitlines():
    ln=ln.strip()
    if not ln or ln.startswith("#"): continue
    p=ln.replace(","," ").split()
    try: vals.append(float(p[1] if len(p)>=2 else p[0]))
    except: pass
n=len(vals)
if n>=2:
    span_ms=vals[-1]-vals[0]
    fps=(n-1)/(span_ms/1000.0) if span_ms else None
    print(f"pts_n={n} first={vals[0]} last={vals[-1]} span_ms={span_ms} fps={fps}")
PY
  else
    echo "no pts"
  fi
done
