#!/bin/bash
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
test -f app/env_log.py
grep -n temp_c app/main.py | head -8
grep -n data-env app/templates/index.html | head -3
.venv/bin/python -m pytest tests/test_env_jsonl.py -q
echo KIOSK_ENV_OK
