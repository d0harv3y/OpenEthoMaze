#!/usr/bin/env python3
"""Ensure this NVR has an ed25519 key and print it for cam authorized_keys.

On NVR:
  python3 push_nvr_ssh_pubkey.py
Then on each cam (once):
  mkdir -p ~/.ssh && chmod 700 ~/.ssh
  echo 'ssh-ed25519 AAAA… root@bhvr-nvr0' >> ~/.ssh/authorized_keys
  chmod 600 ~/.ssh/authorized_keys

Or from a laptop that already has password SSH to the cam:
  ssh admin@CAM 'mkdir -p ~/.ssh && chmod 700 ~/.ssh'
  ssh admin@NVR 'cat ~/.ssh/id_ed25519_bhvr.pub' | ssh admin@CAM 'cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
"""

from __future__ import annotations

import subprocess
from pathlib import Path

KEY = Path.home() / ".ssh" / "id_ed25519_bhvr"
PUB = KEY.with_suffix(".pub")


def main() -> int:
    KEY.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not KEY.is_file():
        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-f",
                str(KEY),
                "-N",
                "",
                "-C",
                "bhvr-nvr-session-control",
            ],
            check=True,
        )
        print(f"generated {KEY}", flush=True)
    else:
        print(f"using existing {KEY}", flush=True)
    print("--- public key (paste into cam ~/.ssh/authorized_keys) ---", flush=True)
    print(PUB.read_text(encoding="utf-8").strip(), flush=True)
    print("--- ssh config Host snippet (optional) ---", flush=True)
    print(
        f"Host bhvr-cam*\n  IdentityFile {KEY}\n  IdentitiesOnly yes\n  StrictHostKeyChecking accept-new",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
