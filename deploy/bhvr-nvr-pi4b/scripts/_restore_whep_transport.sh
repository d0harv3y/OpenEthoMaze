#!/bin/bash
# Litmus scripts sometimes leave transport=mpegts; put Mode2 WHEP back.
set -euxo pipefail
cd "$HOME/bhvr-kiosk"
python3 - <<'PY'
from pathlib import Path
p = Path("config.yaml")
text = p.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
out = []
in_preview = False
seen_transport = False
for ln in lines:
    if ln.strip() == "preview:" or ln.startswith("preview:"):
        in_preview = True
        out.append(ln)
        continue
    if in_preview and ln and not ln[0].isspace() and not ln.startswith("#"):
        in_preview = False
    if in_preview and ln.lstrip().startswith("transport:"):
        indent = ln[: len(ln) - len(ln.lstrip())]
        out.append(f"{indent}transport: whep\n")
        seen_transport = True
        continue
    out.append(ln)
if not seen_transport:
    raise SystemExit("preview.transport not found")
p.write_text("".join(out), encoding="utf-8")
print("patched transport: whep")
PY
grep -E 'transport:|whep_ingest:' config.yaml
pkill -f 'uvicorn app.main:app' 2>/dev/null || true
sleep 1
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 \
  >"$HOME/bhvr-kiosk/uvicorn.log" 2>&1 &
sleep 2
curl -sS http://127.0.0.1:8080/api/health | python3 -c 'import sys,json; h=json.load(sys.stdin); print("transport", h.get("preview_transport"), "idle", h.get("preview_idle"))'
echo RESTORE_WHEP_DONE
