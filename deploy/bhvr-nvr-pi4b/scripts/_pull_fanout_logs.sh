#!/bin/bash
set -uo pipefail
for c in 0 1 2 3; do
  echo "=== cam$c science bytes ==="
  wc -c "/tmp/fanout_bhvr-cam${c}_science.h264" 2>/dev/null || true
  echo "=== cam$c ingest ==="
  tail -10 "/tmp/fanout_bhvr-cam${c}_ingest.log" 2>/dev/null || true
  echo "=== cam$c scale ==="
  tail -25 "/tmp/fanout_bhvr-cam${c}_scale.log" 2>/dev/null || true
done
