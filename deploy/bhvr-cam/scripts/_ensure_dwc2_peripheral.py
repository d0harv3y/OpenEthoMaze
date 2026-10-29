#!/usr/bin/env python3
"""Ensure dtoverlay=dwc2,dr_mode=peripheral is active under [all] in config.txt.

Stock Pi OS parks otg_mode under [cm4] and dwc2 under [cm5]; those filters do
not match Pi Zero W. In-place sed then looks done while UDC stays empty.
"""
from __future__ import annotations

import sys
from pathlib import Path

MARK = "# bhvr-cam USB gadget (CDC ECM toward NVR)"
LINE = "dtoverlay=dwc2,dr_mode=peripheral"


def rewrite(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    section = ""
    for line in lines:
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
                continue  # re-emit under [all] below
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
            text_out = (
                text_out[: idx + 1]
                + "[all]\n"
                + block
                + text_out[idx + 1 + len("[all]") :].lstrip("\n")
            )
        else:
            text_out = text_out.rstrip() + "\n\n[all]\n" + block

    # de-dupe peripheral under [all]
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


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _ensure_dwc2_peripheral.py /boot/firmware/config.txt", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    new = rewrite(path.read_text(encoding="utf-8", errors="replace"))
    path.write_text(new, encoding="utf-8")
    print(f"ensured {LINE} under [all] in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
