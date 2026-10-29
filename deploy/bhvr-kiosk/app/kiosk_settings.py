"""Kiosk settings — fleet ops (USB push, Wi‑Fi, backup, data_root).

Decisions: deploy/bhvr-kiosk/SETTINGS_GRILL.md § Kiosk settings (2026-10-23).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

# Soft fleet set = firstboot scripts/units + gadget *files* (grill Q7=A / Q13=A).
# Does not run install_usb_gadget.sh (no dtoverlay / networkd reconfig mid-push).
SOFT_INSTALL: list[tuple[str, str]] = [
    ("scripts/announce_mqtt.py", "/usr/local/bin/bhvr-cam-announce"),
    ("scripts/find_broker.py", "/usr/local/bin/bhvr-cam-find-broker"),
    ("scripts/clean_broker_override.sh", "/usr/local/bin/bhvr-cam-clean-broker-override"),
    ("scripts/record_h264.sh", "/usr/local/bin/bhvr-cam-record"),
    ("scripts/htu21d.py", "/usr/local/lib/bhvr/htu21d.py"),
    ("scripts/htu21d.py", "/usr/local/bin/bhvr-cam-htu21d"),
    ("scripts/usb_gadget_ecm.sh", "/usr/local/bin/bhvr-cam-usb-gadget"),
    ("systemd/bhvr-cam-announce.service", "/etc/systemd/system/bhvr-cam-announce.service"),
    ("systemd/bhvr-cam-announce.timer", "/etc/systemd/system/bhvr-cam-announce.timer"),
    ("systemd/bhvr-cam-htu-sample.service", "/etc/systemd/system/bhvr-cam-htu-sample.service"),
    ("systemd/bhvr-cam-htu-sample.timer", "/etc/systemd/system/bhvr-cam-htu-sample.timer"),
    ("systemd/bhvr-cam-broker-listen.service", "/etc/systemd/system/bhvr-cam-broker-listen.service"),
    ("systemd/bhvr-cam-record.service", "/etc/systemd/system/bhvr-cam-record.service"),
    ("systemd/bhvr-cam-usb-gadget.service", "/etc/systemd/system/bhvr-cam-usb-gadget.service"),
    ("systemd/bhvr-cam-usb0-dhcp.service", "/etc/systemd/system/bhvr-cam-usb0-dhcp.service"),
    ("network/bhvr-usb0.network", "/etc/systemd/network/bhvr-usb0.network"),
    ("udev/99-bhvr-usb0-dhcp.rules", "/etc/udev/rules.d/99-bhvr-usb0-dhcp.rules"),
]

WIFI_ENV_PATH = Path("/etc/bhvr/wifi.env")
WIFI_CONN_NAME = "bhvr-iot"


def openethomaze_root(cfg: dict[str, Any]) -> Path:
    """Root that contains ``deploy/bhvr-cam`` (grill Q18=A).

    Prefer explicit ``cam_bundle_git_root``. Else ``$HOME/OpenEthoMaze`` when
    that tree exists; else ``$HOME`` when ``$HOME/deploy/bhvr-cam`` is the
    NVR deploy layout (no full OpenEthoMaze clone).
    """
    raw = str(cfg.get("cam_bundle_git_root") or "").strip()
    if raw:
        return Path(raw).expanduser()
    home = Path.home()
    oem = home / "OpenEthoMaze"
    if (oem / "deploy" / "bhvr-cam").is_dir():
        return oem
    if (home / "deploy" / "bhvr-cam").is_dir():
        return home
    return oem


def cam_tree(cfg: dict[str, Any]) -> Path:
    return openethomaze_root(cfg) / "deploy" / "bhvr-cam"


def git_status(repo: Path) -> dict[str, Any]:
    """Return version info for UI (grill Q19=A — dirty OK)."""
    out: dict[str, Any] = {
        "root": str(repo),
        "cam_tree": str(repo / "deploy" / "bhvr-cam"),
        "ok": False,
        "sha": "",
        "describe": "",
        "dirty": False,
        "error": "",
    }
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        # Allow worktree / missing clone
        if not (repo / "deploy" / "bhvr-cam").is_dir():
            out["error"] = f"missing OpenEthoMaze tree at {repo}"
            return out
        out["ok"] = True
        out["describe"] = "no-git"
        out["error"] = "not a git checkout (push still allowed if cam tree exists)"
        return out
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        ).strip()
        try:
            describe = subprocess.check_output(
                ["git", "-C", str(repo), "describe", "--always", "--tags", "--dirty"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=8,
            ).strip()
        except subprocess.CalledProcessError:
            describe = sha
        dirty = bool(
            subprocess.check_output(
                ["git", "-C", str(repo), "status", "--porcelain"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=8,
            ).strip()
        )
        out.update(ok=True, sha=sha, describe=describe, dirty=dirty)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        out["error"] = str(exc)
    return out


def soft_bundle_files(tree: Path) -> list[dict[str, str]]:
    """List soft-set files present under cam tree."""
    rows: list[dict[str, str]] = []
    for rel, dest in SOFT_INSTALL:
        src = tree / rel
        rows.append(
            {
                "rel": rel,
                "dest": dest,
                "present": src.is_file(),
                "bytes": str(src.stat().st_size) if src.is_file() else "0",
            }
        )
    return rows


def eligible_usb_cams(
    cameras: list[dict[str, Any]],
    *,
    ssh_ok: Callable[[str], bool],
) -> list[dict[str, Any]]:
    """ONLINE·USB with USB IP and SSH litmus (grill Q6)."""
    out: list[dict[str, Any]] = []
    for c in cameras:
        if not c.get("online"):
            continue
        if str(c.get("link") or "").lower() != "usb":
            continue
        ips = c.get("ips") if isinstance(c.get("ips"), dict) else {}
        ip = str(ips.get("usb") or c.get("ip") or "").strip()
        if not ip.startswith("192.168.7."):
            continue
        cid = str(c.get("id") or "")
        ok = ssh_ok(ip)
        out.append({"id": cid, "ip": ip, "ssh_ok": ok, "eligible": ok})
    return out


def _ssh_base(cfg: dict[str, Any], host: str) -> list[str]:
    user = cfg.get("ssh_user", "admin")
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=12",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    identity = cfg.get("ssh_identity_file") or ""
    if identity:
        argv.extend(["-i", str(identity), "-o", "IdentitiesOnly=yes"])
    argv.append(f"{user}@{host}")
    return argv


def _scp_base(cfg: dict[str, Any]) -> list[str]:
    argv = [
        "scp",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=12",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    identity = cfg.get("ssh_identity_file") or ""
    if identity:
        argv.extend(["-i", str(identity), "-o", "IdentitiesOnly=yes"])
    return argv


def push_soft_set_to_cam(
    cfg: dict[str, Any],
    *,
    cam_id: str,
    host: str,
    tree: Path,
) -> dict[str, Any]:
    """SCP soft files + sudo tee install on one cam. Does not run gadget install."""
    log: list[str] = []
    missing = [rel for rel, _ in SOFT_INSTALL if not (tree / rel).is_file()]
    if missing:
        return {
            "id": cam_id,
            "ip": host,
            "ok": False,
            "log": [f"missing in tree: {', '.join(missing[:8])}"],
        }

    user = cfg.get("ssh_user", "admin")
    remote_dir = "/tmp/bhvr-cam-soft"
    # Clear + mkdir on cam (user-writable)
    r = subprocess.run(
        [*_ssh_base(cfg, host), f"rm -rf {remote_dir} && mkdir -p {remote_dir}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if r.returncode != 0:
        return {
            "id": cam_id,
            "ip": host,
            "ok": False,
            "log": [f"mkdir failed: {(r.stderr or r.stdout or '').strip()}"],
        }

    # Stage unique basenames locally — plain scp keeps source leaf names, and
    # htu21d.py is installed to two destinations.
    staged: list[tuple[str, str]] = []  # (remote_base, dest)
    with tempfile.TemporaryDirectory(prefix="bhvr-soft-") as td:
        tdir = Path(td)
        for i, (rel, dest) in enumerate(SOFT_INSTALL):
            src = tree / rel
            base = f"{i:02d}_{Path(rel).name}"
            shutil.copy2(src, tdir / base)
            staged.append((base, dest))
        scp_args = (
            [*_scp_base(cfg)]
            + [str(tdir / base) for base, _ in staged]
            + [f"{user}@{host}:{remote_dir}/"]
        )
        r = subprocess.run(scp_args, capture_output=True, text=True, timeout=120, check=False)
        if r.returncode != 0:
            return {
                "id": cam_id,
                "ip": host,
                "ok": False,
                "log": [f"scp failed: {(r.stderr or r.stdout or '').strip()}"],
            }
    log.append(f"scp {len(staged)} files OK")

    # Install via ``cat | sudo tee`` (firstboot NOPASSWD). Do NOT use
    # ``sudo tee <file`` under ``ssh … bash -s`` — tee then reads the script
    # pipe and hangs. Prefer full paths for sudoers matching.
    lines = [
        "set -euo pipefail",
        "sudo /bin/mkdir -p /usr/local/lib/bhvr /etc/systemd/system /etc/systemd/network /etc/udev/rules.d",
    ]
    for base, dest in staged:
        lines.append(
            f"cat {remote_dir}/{base} | sudo /usr/bin/tee {dest} >/dev/null"
        )
        # Older images may lack chmod NOPASSWD — never block on password prompt.
        if dest.startswith("/usr/local/bin/") or dest.endswith(".sh"):
            lines.append(f"sudo -n /bin/chmod 755 {dest} 2>/dev/null || true")
    # Avoid ``enable --now`` / restarting broker-listen (find-broker --timeout 0
    # never exits; try-restart blocks). Timers only + one-shot announce.
    lines += [
        "sudo /bin/systemctl daemon-reload",
        "sudo /bin/systemctl restart bhvr-cam-announce.timer 2>/dev/null || true",
        "sudo /bin/systemctl restart bhvr-cam-htu-sample.timer 2>/dev/null || true",
        "timeout -k 2 8 python3 /usr/local/bin/bhvr-cam-announce >/tmp/bhvr-announce-push.out 2>&1 || true",
        "tail -1 /tmp/bhvr-announce-push.out || true",
        "echo PUSH_OK",
    ]
    script = "\n".join(lines) + "\n"
    r = subprocess.run(
        [*_ssh_base(cfg, host), "bash", "-s"],
        input=script,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0 or "PUSH_OK" not in out:
        log.append(out or err or f"exit {r.returncode}")
        if err:
            log.append(err)
        return {"id": cam_id, "ip": host, "ok": False, "log": log}
    for line in out.splitlines():
        if line.strip():
            log.append(line.strip())
    return {"id": cam_id, "ip": host, "ok": True, "log": log}


def write_wifi_env(ssid: str, password: str, *, hidden: bool = False) -> tuple[bool, str]:
    """Persist NVR copy via sudo tee (grill Q8=A). Never returned by GET APIs."""
    body = (
        f"SSID={ssid}\n"
        f"PASSWORD={password}\n"
        f"HIDDEN={'1' if hidden else '0'}\n"
        f"CONN={WIFI_CONN_NAME}\n"
    )
    subprocess.run(
        ["sudo", "-n", "mkdir", "-p", str(WIFI_ENV_PATH.parent)],
        capture_output=True,
        text=True,
        check=False,
    )
    r = subprocess.run(
        ["sudo", "-n", "tee", str(WIFI_ENV_PATH)],
        input=body,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "tee wifi.env failed").strip()
    subprocess.run(
        ["sudo", "-n", "chmod", "600", str(WIFI_ENV_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )
    return True, str(WIFI_ENV_PATH)


def nmcli_wifi_apply_local(ssid: str, password: str, *, hidden: bool = False) -> tuple[bool, str]:
    """Apply bhvr-iot on NVR via nmcli (needs privileges)."""
    # Delete old connection if present
    subprocess.run(
        ["sudo", "-n", "nmcli", "connection", "delete", WIFI_CONN_NAME],
        capture_output=True,
        text=True,
        check=False,
    )
    cmd = [
        "sudo",
        "-n",
        "nmcli",
        "connection",
        "add",
        "type",
        "wifi",
        "con-name",
        WIFI_CONN_NAME,
        "ifname",
        "wlan0",
        "ssid",
        ssid,
        "--",
        "wifi-sec.key-mgmt",
        "wpa-psk",
        "wifi-sec.psk",
        password,
    ]
    if hidden:
        cmd.extend(["wifi.hidden", "yes"])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or f"exit {r.returncode}").strip()
    r2 = subprocess.run(
        ["sudo", "-n", "nmcli", "connection", "up", WIFI_CONN_NAME],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if r2.returncode != 0:
        return False, (r2.stderr or r2.stdout or "up failed").strip()
    return True, "NVR Wi‑Fi up"


def push_wifi_to_cam(
    cfg: dict[str, Any],
    *,
    host: str,
    ssid: str,
    password: str,
    hidden: bool = False,
) -> tuple[bool, str]:
    """Push NM wifi profile to cam over SSH (USB preferred)."""
    # Cam firstboot sudoers covers tee/systemctl; nmcli may need NVR-style sudoers
    # on older images — try sudo -n nmcli, fall back to plain nmcli.
    hidden_flag = "yes" if hidden else "no"
    remote = f"""set -euo pipefail
NM="nmcli"
if sudo -n nmcli -t -f NAME connection show >/dev/null 2>&1; then NM="sudo -n nmcli"; fi
$NM connection delete {WIFI_CONN_NAME} 2>/dev/null || true
$NM connection add type wifi con-name {WIFI_CONN_NAME} ifname wlan0 ssid {_shell_quote(ssid)} \\
  -- wifi-sec.key-mgmt wpa-psk wifi-sec.psk {_shell_quote(password)} wifi.hidden {hidden_flag}
$NM connection up {WIFI_CONN_NAME}
echo WIFI_OK
"""
    r = subprocess.run(
        [*_ssh_base(cfg, host), "bash", "-s"],
        input=remote,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    out = (r.stdout or "").strip()
    if r.returncode != 0 or "WIFI_OK" not in out:
        return False, (r.stderr or out or f"exit {r.returncode}").strip()
    return True, "cam Wi‑Fi profile up"


def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def list_session_folders(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(root.glob("ses-*"), reverse=True):
        if not p.is_dir():
            continue
        try:
            size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        except OSError:
            size = 0
        rows.append({"name": p.name, "path": str(p), "bytes": size})
    # Also under one-level subdirs (output_subdir)
    for sub in sorted(root.iterdir()):
        if not sub.is_dir() or sub.name.startswith("ses-") or sub.name.startswith("."):
            continue
        for p in sorted(sub.glob("ses-*"), reverse=True):
            if not p.is_dir():
                continue
            try:
                size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            except OSError:
                size = 0
            rows.append(
                {
                    "name": f"{sub.name}/{p.name}",
                    "path": str(p),
                    "bytes": size,
                }
            )
    return rows


def backup_sessions_cifs(
    *,
    unc: str,
    username: str,
    password: str,
    session_paths: list[str],
) -> dict[str, Any]:
    """Mount CIFS on demand, copy sessions, unmount (grill Q17=A, Q11=B)."""
    log: list[str] = []
    # Normalize UNC → //host/share/path
    share = unc.strip().replace("\\", "/")
    if not share.startswith("//"):
        share = "//" + share.lstrip("/")
    mnt = Path(tempfile.mkdtemp(prefix="bhvr-backup-"))
    cred = Path(tempfile.mkstemp(prefix="bhvr-cifs-", suffix=".cred")[1])
    try:
        cred.write_text(
            f"username={username}\npassword={password}\n",
            encoding="utf-8",
        )
        os.chmod(cred, 0o600)
        r = subprocess.run(
            [
                "sudo",
                "-n",
                "mount",
                "-t",
                "cifs",
                share,
                str(mnt),
                "-o",
                f"credentials={cred},uid={os.getuid()},gid={os.getgid()},iocharset=utf8,file_mode=0644,dir_mode=0755",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if r.returncode != 0:
            return {
                "ok": False,
                "log": [f"mount failed: {(r.stderr or r.stdout or '').strip()}"],
            }
        log.append(f"mounted {share}")
        dest_root = mnt / "bhvr-backup"
        dest_root.mkdir(parents=True, exist_ok=True)
        for sp in session_paths:
            src = Path(sp)
            if not src.is_dir():
                log.append(f"skip missing {sp}")
                continue
            dest = dest_root / src.name
            # copytree into unique name if exists
            if dest.exists():
                dest = dest_root / f"{src.name}_{int(time.time())}"
            shutil.copytree(src, dest, dirs_exist_ok=False)
            log.append(f"copied {src.name} → {dest.name}")
        return {"ok": True, "log": log}
    except Exception as exc:
        return {"ok": False, "log": log + [str(exc)]}
    finally:
        subprocess.run(
            ["sudo", "-n", "umount", str(mnt)],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            mnt.rmdir()
        except OSError:
            pass
        try:
            cred.unlink(missing_ok=True)
        except OSError:
            pass


def restart_kiosk_web() -> tuple[bool, str]:
    """Best-effort restart of kiosk uvicorn / user unit."""
    r = subprocess.run(
        ["systemctl", "--user", "restart", "bhvr-kiosk-web.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode == 0:
        return True, "restarted user unit bhvr-kiosk-web.service"
    r2 = subprocess.run(
        ["sudo", "-n", "systemctl", "restart", "bhvr-kiosk-web.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r2.returncode == 0:
        return True, "restarted system unit bhvr-kiosk-web.service"
    # Last resort: kill uvicorn (install scripts often use nohup)
    subprocess.run(["pkill", "-f", "uvicorn app.main:app"], check=False)
    return (
        False,
        "killed uvicorn if present — start manually: "
        "cd ~/bhvr-kiosk && nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 &",
    )
