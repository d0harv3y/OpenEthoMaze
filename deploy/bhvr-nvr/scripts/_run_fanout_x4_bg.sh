#!/bin/bash
NVR="${HOME}/deploy/bhvr-nvr"
sed -i 's/\r$//' "$NVR/scripts/_litmus_fanout_x4.sh" || true
pkill -f '_litmus_fanout_x4.sh' 2>/dev/null || true
sleep 1
nohup env DURATION_S=8 DUR_ENCODE=20 bash "$NVR/scripts/_litmus_fanout_x4.sh" \
  > /tmp/fanout_x4_run.log 2>&1 &
echo $! > /tmp/fanout_x4_run.pid
echo "started pid=$(cat /tmp/fanout_x4_run.pid)"
sleep 3
head -30 /tmp/fanout_x4_run.log || true
