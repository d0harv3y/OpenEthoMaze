#!/bin/bash
# Push current htu21d + 1 Hz sampler to cam2/cam3 (fixes announce window_stats skew).
#
# Same path as yesterday's _push_htu_1hz.sh / _deploy_htu21d.sh:
#   BatchMode SSH + sudo tee/systemctl (NOPASSWD via /etc/sudoers.d/bhvr-cam).
# No interactive password when that drop-in exists. cam2/3 currently lack it —
# then run from a real TTY:  ssh -t …  (or install sudoers once; see REMOTE).
set -euo pipefail
KEY=(-i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes -o BatchMode=yes
     -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new)
for f in /tmp/htu21d.py /tmp/bhvr-cam-htu-sample.service /tmp/bhvr-cam-htu-sample.timer; do
  test -f "$f" || { echo "missing $f — scp from laptop first"; exit 1; }
done

for ip in 192.168.7.31 192.168.7.28; do
  echo "======== $ip ========"
  scp "${KEY[@]}" /tmp/htu21d.py /tmp/bhvr-cam-htu-sample.service /tmp/bhvr-cam-htu-sample.timer \
    "admin@$ip:/tmp/"
  # Prefer passwordless (yesterday). If tee needs a password, fall back to -t
  # only when stdin is a TTY (heredoc+ssh -t otherwise prints "Pseudo-terminal
  # will not be allocated" and still can't prompt).
  if ssh "${KEY[@]}" "admin@$ip" 'sudo -n /usr/bin/tee /dev/null </dev/null' 2>/dev/null; then
    SSH_CMD=(ssh "${KEY[@]}" "admin@$ip")
  elif [[ -t 0 ]]; then
    echo "NOTE: no NOPASSWD tee on $ip — prompting for sudo password" >&2
    SSH_CMD=(ssh -t -i "$HOME/.ssh/id_ed25519_bhvr" -o IdentitiesOnly=yes \
      -o ConnectTimeout=12 "admin@$ip")
  else
    echo "FAIL: $ip has no /etc/sudoers.d/bhvr-cam NOPASSWD for tee, and stdin is not a TTY." >&2
    echo "  Fix once (on NVR, interactive):" >&2
    echo "    ssh -t -i ~/.ssh/id_ed25519_bhvr -o IdentitiesOnly=yes admin@$ip" >&2
    echo "    # then paste install block, or re-run: bash /tmp/_push_htu_cam23.sh" >&2
    exit 1
  fi
  "${SSH_CMD[@]}" bash -s <<'REMOTE'
set -euo pipefail
# Install path matches firstboot NOPASSWD: tee/mkdir/chmod/systemctl only.
# Do NOT sudo python3 (not in NOPASSWD list).
# NOPASSWD on these images: tee/mkdir/systemctl — NOT chmod/python (see _deploy_htu21d.sh).
sudo mkdir -p /usr/local/lib/bhvr
sudo tee /usr/local/lib/bhvr/htu21d.py >/dev/null </tmp/htu21d.py
sudo tee /usr/local/bin/bhvr-cam-htu21d >/dev/null </tmp/htu21d.py
sudo tee /etc/systemd/system/bhvr-cam-htu-sample.service >/dev/null </tmp/bhvr-cam-htu-sample.service
sudo tee /etc/systemd/system/bhvr-cam-htu-sample.timer >/dev/null </tmp/bhvr-cam-htu-sample.timer
sudo systemctl daemon-reload
sudo systemctl enable --now bhvr-cam-htu-sample.timer
sudo systemctl start bhvr-cam-htu-sample.service || true
sleep 2
for _ in 1 2 3 4 5 6 7 8 9 10; do
  python3 /usr/local/bin/bhvr-cam-htu21d sample || true
  sleep 1
done
python3 /usr/local/bin/bhvr-cam-htu21d || true
python3 /usr/local/bin/bhvr-cam-announce || true
hostname
systemctl is-active bhvr-cam-htu-sample.timer
REMOTE
done

echo "=== roster ==="
sleep 2
curl -sS -m 8 http://127.0.0.1:8080/api/cams | python3 -c '
import json,sys
for c in json.load(sys.stdin).get("cameras",[]):
    if c.get("id") in ("bhvr-cam2","bhvr-cam3"):
        print(c["id"], "temp=", c.get("temp_c"), "env=", bool(c.get("env")), "age=", c.get("age_s"))
'
echo DONE
