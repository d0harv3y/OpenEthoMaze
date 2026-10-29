#!/usr/bin/env python3
"""Rewrite Pi config.txt → /tmp/config.txt.bhvr with dwc2 peripheral under [all].

See deploy/bhvr-cam/scripts/_ensure_dwc2_peripheral.py for the rule.
"""
from pathlib import Path

MARK = "# bhvr-cam USB gadget (CDC ECM toward NVR)"
LINE = "dtoverlay=dwc2,dr_mode=peripheral"


def rewrite(text: str) -> str:
    out: list[str] = []
    section = ""
    for line in text.splitlines(keepends=True):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip().lower()
            out.append(line)
            continue
        if s.startswith("otg_mode=1"):
            out.append("# bhvr: otg_mode=1 breaks Pi Zero dwc2 UDC\n")
            out.append("#otg_mode=1\n")
            continue
        if s.startswith("dtoverlay=dwc2"):
            if section in ("", "all"):
                continue
            out.append(f"# bhvr: moved dwc2 to all-section (was under [{section}])\n")
            continue
        if s == MARK:
            continue
        out.append(line)

    text_out = "".join(out)
    block = f"{MARK}\n{LINE}\n"
    # Match section header only — comments may contain the substring "[all]".
    if LINE not in text_out:
        idx = text_out.find("\n[all]")
        if text_out.startswith("[all]"):
            text_out = "[all]\n" + block + text_out[len("[all]") :].lstrip("\n")
        elif idx >= 0:
            text_out = text_out[: idx + 1] + "[all]\n" + block + text_out[idx + 1 + len("[all]") :].lstrip(
                "\n"
            )
        else:
            text_out = text_out.rstrip() + "\n\n[all]\n" + block

    cleaned: list[str] = []
    section = ""
    n = 0
    for line in text_out.splitlines(keepends=True):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip().lower()
            cleaned.append(line)
            continue
        if section == "all" and s == LINE:
            n += 1
            if n > 1:
                continue
        cleaned.append(line)
    return "".join(cleaned)


for f in (Path("/boot/firmware/config.txt"), Path("/boot/config.txt")):
    if not f.is_file():
        continue
    new = rewrite(f.read_text(encoding="utf-8", errors="replace"))
    Path("/tmp/config.txt.bhvr").write_text(new, encoding="utf-8")
    print(f"ok from {f}")
    for i, line in enumerate(new.splitlines(), 1):
        s = line.strip()
        if s.startswith("[") or "otg_mode" in s or "dwc2" in s or "bhvr-cam USB" in s:
            print(f"{i}:{line}")
    break
else:
    raise SystemExit("no config.txt")
