#!/usr/bin/env python3
"""Ensure dtparam=i2c_arm=on + i2c-dev module load (HTU21D)."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_i2c(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    if any("dtparam=i2c_arm=on" in ln and not ln.strip().startswith("#") for ln in lines):
        print(f"i2c_arm already on in {path}")
        return False
    # Prefer under [all]; append if missing.
    out: list[str] = []
    inserted = False
    in_all = False
    for ln in lines:
        if ln.strip().lower() == "[all]":
            in_all = True
            out.append(ln)
            continue
        if ln.strip().startswith("[") and ln.strip().endswith("]"):
            if in_all and not inserted:
                out.append("dtparam=i2c_arm=on\n")
                inserted = True
            in_all = False
        out.append(ln)
    if in_all and not inserted:
        out.append("dtparam=i2c_arm=on\n")
        inserted = True
    if not inserted:
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        out.append("\n[all]\ndtparam=i2c_arm=on\n")
        inserted = True
    path.write_text("".join(out), encoding="utf-8")
    print(f"added dtparam=i2c_arm=on → {path}")
    return True


def ensure_i2c_dev_module() -> None:
    """Create /dev/i2c-* nodes (dtparam alone loads bcm2835 but not i2c-dev)."""
    conf = Path("/etc/modules-load.d/i2c-dev.conf")
    try:
        conf.parent.mkdir(parents=True, exist_ok=True)
        body = conf.read_text(encoding="utf-8") if conf.is_file() else ""
        if any(ln.strip() == "i2c-dev" for ln in body.splitlines()):
            print(f"i2c-dev already in {conf}")
            return
        with conf.open("a", encoding="utf-8") as f:
            if body and not body.endswith("\n"):
                f.write("\n")
            f.write("i2c-dev\n")
        print(f"added i2c-dev → {conf}")
    except OSError as exc:
        print(f"WARN: could not write {conf}: {exc}", file=sys.stderr)


def main() -> int:
    ensure_i2c_dev_module()
    for candidate in (
        Path("/boot/firmware/config.txt"),
        Path("/boot/config.txt"),
    ):
        if candidate.is_file():
            ensure_i2c(candidate)
            return 0
    print("WARN: no config.txt — enable i2c_arm manually", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
