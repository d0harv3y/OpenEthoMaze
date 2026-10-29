"""Session console — MQTT roster grid + wireless acquisition + focus live preview."""

from __future__ import annotations

import asyncio
import json
import queue
import re
import select
import statistics
import subprocess
import threading
import time
from collections import deque
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.capture_stats import (
    new_capture_byte_stats,
    note_capture_bytes,
    snapshot_capture_stats,
)
from app.env_log import append_env_jsonl
from app.encode_ask import (
    DEFAULT_SCIENCE_FPS,
    DEFAULT_SCIENCE_SIZE,
    SCIENCE_FPS_OPTIONS,
    SCIENCE_SIZE_IDS,
    encode_ask,
    normalize_science_size,
    normalize_soft_fps,
    science_encode_ask,
    science_size_options,
)
from app.operator_state import (
    CHUNK_DEFAULT_LITE_MIN,
    CHUNK_DEFAULT_STANDARD_MIN,
    chunk_preset_minutes,
    estimate_gb_per_hour,
    list_output_subdirs,
    load_operator_state,
    patch_cam_meta,
    save_operator_state,
    session_folder,
    storage_health,
)
from app.preview import (
    SENSOR_MODE_IDS,
    SENSOR_MODE_LABELS,
    PreviewSettings,
    cam_free_encode_remote,
    cam_live_annexb_remote,
    cam_live_ssh_mpegts_remote,
    cam_live_udp_remote,
    cam_science_ssh_mpegts_remote,
    cam_stop_udp_remote,
    cam_udp_port,
    feed_queue_to_iterator,
    idle_rpicam_remote,
    mediamtx_whep_url,
    nvr_ffmpeg_annexb_to_mediamtx_udp,
    nvr_ffmpeg_udp_to_mpegts_pipe,
    nvr_ingress_ip,
    preview_settings,
)
from app import kiosk_settings, webrtc_preview

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
CONFIG_PATH = ROOT / "config.yaml"
EXAMPLE_PATH = ROOT / "config.example.yaml"
TEMPLATES = Jinja2Templates(directory=str(APP_DIR / "templates"))
STATIC_DIR = APP_DIR / "static"

app = FastAPI(title="bhvr-kiosk", version="0.8.0")
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_roster_lock = threading.Lock()
_roster: dict[str, dict[str, Any]] = {}
_mqtt_thread: threading.Thread | None = None
# NVR-local capture: cam_id -> {proc, stderr, host, h264, stop, writer, stats, …}
_capture_lock = threading.Lock()
_captures: dict[str, dict[str, Any]] = {}
# Idle TCP-listen previews: cam_id -> {ffmpeg, host, stop}
_preview_lock = threading.Lock()
_idle_previews: dict[str, dict[str, Any]] = {}
# While recording: optional H.264 chunk sink for focus remux
_record_preview_sinks: dict[str, "queue.Queue[bytes | None]"] = {}
# Browser live-player diag (mpegts.js knobs / buffered-ahead). Ring for litmus.
_live_player_lock = threading.Lock()
_live_player_samples: deque[dict[str, Any]] = deque(maxlen=800)


class LivePlayerSample(BaseModel):
    """Client report: MSE buffered-ahead + stream fps under chase/stash knobs."""

    cam_id: str
    chase: bool = False
    stash: int = 128
    paint_n: int = 1  # always paint every decoded frame (decimate slider removed)
    buffered_s: float | None = None
    stream_fps: float | None = None
    ts_ms: int | None = None

# Science size tokens (4:3). Soft fps is session-owned; achieved rate is pts/fps.json.
# Legacy 480p/720p/1080p aliases normalize via encode_ask.normalize_science_size.
PROFILE_GEOM: dict[str, tuple[int, int]] = {
    "standard": (1296, 972),
    "lite": (640, 480),
    # legacy
    "1080p": (1296, 972),
    "720p": (1296, 972),
    "480p": (640, 480),
    "720p30": (1296, 972),
    "720p20": (1296, 972),
    "480p30": (640, 480),
}

# User-writable path on cam (avoids passwordless-sudo dependency).
CAM_WORKDIR = "~/bhvr-current"


class SubjectMeta(BaseModel):
    """DANDI-oriented fields + local cage extras (written to meta.json)."""

    subject_id: str = Field(min_length=1)
    species: str = "Mus musculus"
    sex: str = Field(pattern=r"^[MFU]$")
    age: str = ""
    date_of_birth: str = ""
    strain: str = ""
    cage_id: str = ""
    protocol: str = "cage_night"
    profile: str = DEFAULT_SCIENCE_SIZE  # standard | lite
    soft_fps: int = DEFAULT_SCIENCE_FPS
    notes: str = ""
    camera_ids: list[str] = Field(default_factory=list)


def load_config() -> dict[str, Any]:
    path = CONFIG_PATH if CONFIG_PATH.is_file() else EXAMPLE_PATH
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(cfg: dict[str, Any]) -> None:
    """Persist kiosk config.yaml (creates file even if only example existed)."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def data_root() -> Path:
    return Path(load_config().get("data_root", "/data/bhvr"))


def record_settings(cfg: dict[str, Any]) -> tuple[int, int]:
    """Opportunistic encode knobs for wlan stream (not session FPS claims).

    Returns (soft_fps, bitrate_bps).
    """
    raw = cfg.get("record") or {}
    soft_fps = max(1, int(raw.get("soft_fps", 10)))
    bitrate_bps = max(100_000, int(raw.get("bitrate_kbps", 1200)) * 1000)
    return soft_fps, bitrate_bps


def active_path() -> Path:
    return data_root() / ".active_session.json"


def _active_session_camera_ids() -> set[str]:
    """Cams claimed by the on-disk session (survives uvicorn restart; in-memory may not)."""
    path = active_path()
    if not path.is_file():
        return set()
    try:
        active = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    ids = active.get("meta", {}).get("camera_ids") or []
    return {str(x) for x in ids}


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s.strip()).strip("-") or "unknown"


def session_dir(meta: SubjectMeta, start: datetime) -> Path:
    """Flat ``ses-<utc>/`` under data_root[/output_subdir] (grill Q14=B)."""
    _ = meta
    st = load_operator_state(data_root())
    ses = start.strftime("%Y%m%dT%H%M%SZ")
    return session_folder(data_root(), str(st.get("output_subdir") or ""), ses)


def live_preview_settings(
    cfg: dict[str, Any], *, cam_id: str | None = None
) -> PreviewSettings:
    """Idle live uses Session settings size×fps (grill Q2=A), not fixed Lite@10."""
    base = preview_settings(cfg, cam_id=cam_id)
    st = load_operator_state(data_root())
    ask = encode_ask(
        st["profile"],
        st["soft_fps"],
        cfg=cfg,
        buffer_count=base.buffer_count,
    )
    return replace(
        base,
        width=ask.width,
        height=ask.height,
        fps_idle=ask.soft_fps,
        fps_record=ask.soft_fps,
        bitrate_kbps=ask.bitrate_kbps,
        sensor_mode=ask.sensor_mode,
        buffer_count=ask.buffer_count,
    )


def part_stem(subject_id: str, cam_id: str, part: int = 0) -> str:
    return f"{slug(subject_id)}__{slug(cam_id)}__p{int(part):03d}"


def _coerce_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _maybe_append_env_jsonl(
    cam_id: str,
    *,
    ts: str | None,
    env: dict[str, Any] | None = None,
    temp_c: float | None = None,
    rh_pct: float | None = None,
) -> None:
    """While REC: append HTU21D window min/max/mean to ``{subject}__{cam}_env.jsonl``."""
    try:
        append_env_jsonl(
            active_path=active_path(),
            cam_id=cam_id,
            ts=ts,
            env=env,
            temp_c=temp_c,
            rh_pct=rh_pct,
            load_operator_cameras=lambda: load_operator_state(data_root()).get("cameras")
            or {},
        )
    except OSError as exc:
        print(f"env jsonl append {cam_id}: {exc}", flush=True)


def announce_link_mode(ip: str, link_hint: str | None = None) -> str:
    """How the cam is reaching the NVR for announce/LIVE SSH.

    Prefer explicit MQTT ``link`` when present; else infer from roster IP.
    USB gadget tether uses ``192.168.7.0/24``; WSU-IoT Wi‑Fi is typically ``10.x``.
    """
    hint = (link_hint or "").strip().lower()
    if hint in ("usb", "wifi"):
        return hint
    ip = (ip or "").strip()
    if ip.startswith("192.168.7."):
        return "usb"
    if ip.startswith("10."):
        return "wifi"
    return "other"


def ssh_connect_timeout_for_host(host: str, *, mismatch: bool = False) -> int:
    """Grill Q12: WiFi paths need longer ConnectTimeout (IoT RTT often 500ms+).

    ``mismatch``: host is the non-active backhaul (e.g. USB IP while link=wifi).
    Fail fast — after unplug, waiting 15–30s×3 on a dead USB IP is what makes
    LIVE feel minutes late even though MQTT already flipped.
    """
    if mismatch:
        return 3
    h = (host or "").strip()
    if h.startswith("192.168.7."):
        return 15
    return 30


def online_cameras(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    stale = float(cfg.get("mqtt", {}).get("stale_after_s", 180))
    owned = set(cfg.get("owned_camera_ids") or [])
    now = time.time()
    out: list[dict[str, Any]] = []
    with _roster_lock:
        for cam_id, row in sorted(_roster.items()):
            if owned and cam_id not in owned:
                continue
            age = now - float(row.get("seen_at", 0))
            ip = str(row.get("ip") or "")
            link = announce_link_mode(ip, str(row.get("link") or "") or None)
            out.append(
                {
                    **row,
                    "id": cam_id,
                    "age_s": round(age, 1),
                    "online": age <= stale,
                    "link": link,
                }
            )
    return out


def _ssh_argv(
    cfg: dict[str, Any], host: str, *, mismatch: bool = False
) -> list[str]:
    user = cfg.get("ssh_user", "admin")
    timeout = ssh_connect_timeout_for_host(host, mismatch=mismatch)
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={timeout}",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    identity = cfg.get("ssh_identity_file") or ""
    if identity:
        argv.extend(["-i", str(identity), "-o", "IdentitiesOnly=yes"])
    argv.append(f"{user}@{host}")
    return argv


def _roster_hosts_for_cam(cfg: dict[str, Any], cam_id: str) -> list[str]:
    """Active backhaul first; opposite path last (fail-fast mismatch timeouts).

    When MQTT ``link=wifi``, try WiFi addresses before any USB IP so LIVE does
    not burn ConnectTimeout on a just-unplugged ``192.168.7.x``.
    """
    by_id = {c["id"]: c for c in online_cameras(cfg)}
    cam = by_id.get(cam_id) or {}
    link = str(cam.get("link") or "").strip().lower()
    primary = str(cam.get("ip") or "").strip()
    ips = cam.get("ips") if isinstance(cam.get("ips"), dict) else {}
    usb = str(ips.get("usb") or "").strip()
    wifi = str(ips.get("wifi") or "").strip()
    hosts: list[str] = []

    def add(h: str) -> None:
        h = (h or "").strip()
        if h and h not in hosts:
            hosts.append(h)

    if link == "wifi":
        add(primary if primary.startswith("10.") else "")
        add(wifi)
        add(primary)
        add(usb)
    elif link == "usb":
        add(primary if primary.startswith("192.168.7.") else "")
        add(usb)
        add(primary)
        add(wifi)
    else:
        add(primary)
        add(wifi)
        add(usb)
    return hosts


def _host_mismatches_link(host: str, link: str) -> bool:
    """True when host is clearly the other backhaul vs MQTT link."""
    link = (link or "").strip().lower()
    h = (host or "").strip()
    if link == "wifi" and h.startswith("192.168.7."):
        return True
    if link == "usb" and h.startswith("10."):
        return True
    return False


def _popen_ssh_bash_s(
    cfg: dict[str, Any],
    host: str,
    script: str,
    *,
    err_f: Any,
    extra_ssh: list[str] | None = None,
    mismatch: bool = False,
) -> subprocess.Popen[bytes]:
    """SSH ``bash -s`` with ``script`` on stdin (reliable MPEG-TS pipelines)."""
    argv = [
        *_ssh_argv(cfg, host, mismatch=mismatch),
        *(extra_ssh or []),
        "bash",
        "-s",
    ]
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=err_f,
        bufsize=0,
    )
    assert proc.stdin is not None
    payload = script if script.endswith("\n") else script + "\n"
    proc.stdin.write(payload.encode("utf-8"))
    proc.stdin.close()
    return proc


def _ssh_run(
    cfg: dict[str, Any],
    host: str,
    remote: str,
    timeout: float = 60,
    *,
    mismatch: bool = False,
) -> tuple[int, str]:
    try:
        r = subprocess.run(
            [*_ssh_argv(cfg, host, mismatch=mismatch), remote],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, f"ssh error: {exc}"
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    detail = out if out else err
    if r.returncode != 0 and err and out:
        detail = f"{out} | {err}"
    elif r.returncode != 0:
        detail = detail or f"exit {r.returncode}"
    return r.returncode, detail


def _ssh_litmus(
    cfg: dict[str, Any],
    host: str,
    *,
    attempts: int = 2,
    mismatch: bool = False,
) -> tuple[bool, str]:
    """Grill Q11 R1: retry SSH with backoff (caller may re-resolve hosts)."""
    last = ""
    attempts = 1 if mismatch else max(1, attempts)
    for i in range(attempts):
        code, detail = _ssh_run(
            cfg,
            host,
            "hostname",
            timeout=float(ssh_connect_timeout_for_host(host, mismatch=mismatch) + 5),
            mismatch=mismatch,
        )
        if code == 0 and detail.strip():
            return True, detail.strip()
        last = detail or f"exit {code}"
        if not mismatch and i + 1 < attempts:
            time.sleep(0.35 * (i + 1))
    return False, last


def _resolve_reachable_cam_host(cfg: dict[str, Any], cam_id: str) -> tuple[str | None, str]:
    """Try active backhaul then alternates; return (host, detail)."""
    hosts = _roster_hosts_for_cam(cfg, cam_id)
    if not hosts:
        return None, "no roster ip"
    by_id = {c["id"]: c for c in online_cameras(cfg)}
    link = str((by_id.get(cam_id) or {}).get("link") or "")
    errors: list[str] = []
    for host in hosts:
        mismatch = _host_mismatches_link(host, link)
        # Primary path: 2 tries; mismatch alternates: 1 fast fail.
        ok, detail = _ssh_litmus(cfg, host, attempts=2, mismatch=mismatch)
        if ok:
            return host, detail
        errors.append(f"{host}: {detail}")
    return None, "; ".join(errors)


def _capture_pid_path(folder: Path) -> Path:
    return folder / ".capture_pids.json"


def _save_capture_pids(folder: Path) -> None:
    with _capture_lock:
        payload = {
            cam_id: {"pid": int(info["proc"].pid), "host": info.get("host")}
            for cam_id, info in _captures.items()
            if info.get("proc") is not None
        }
    _capture_pid_path(folder).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _free_cam_encode_hosts(
    cfg: dict[str, Any],
    cam_id: str,
    hosts: list[str] | None = None,
    *,
    link: str = "",
) -> None:
    """pkill rpicam/ffmpeg on cam host(s). Skips cams in an active science session.

    Alternate (mismatch) hosts use a short ConnectTimeout so a dead USB IP after
    unplug cannot stall whep/start for 15–30s and black the browser.
    """
    if cam_id in _active_session_camera_ids():
        return
    if hosts is None:
        hosts = _roster_hosts_for_cam(cfg, cam_id)
    if not link:
        by_id = {c["id"]: c for c in online_cameras(cfg)}
        link = str((by_id.get(cam_id) or {}).get("link") or "")
    seen: set[str] = set()
    for host in hosts:
        h = (host or "").strip()
        if not h or h in seen:
            continue
        seen.add(h)
        mismatch = _host_mismatches_link(h, link)
        try:
            _ssh_run(
                cfg,
                h,
                cam_free_encode_remote(),
                timeout=float(ssh_connect_timeout_for_host(h, mismatch=mismatch) + 2),
                mismatch=mismatch,
            )
        except Exception:
            pass


def _stop_idle_preview(cam_id: str, cfg: dict[str, Any] | None = None) -> None:
    with _preview_lock:
        info = _idle_previews.pop(cam_id, None)
    if not info:
        return
    stop = info.get("stop")
    if isinstance(stop, threading.Event):
        stop.set()
    host = str(info.get("host") or "")
    for key in ("ffmpeg", "proc", "cam_proc"):
        proc = info.get(key)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    for fh in (info.get("stderr"), info.get("cam_stderr")):
        try:
            if fh:
                fh.close()
        except Exception:
            pass
    feeder = info.get("feeder")
    if isinstance(feeder, threading.Thread) and feeder.is_alive():
        feeder.join(timeout=2)
    # Best-effort remote cleanup on the SSH host we were using (not every IP —
    # scanning a dead USB path blocked LIVE for all tiles).
    if (
        host
        and cfg
        and cam_id not in _active_session_camera_ids()
    ):
        try:
            _free_cam_encode_hosts(cfg, cam_id, [host])
        except Exception:
            pass


def stop_all_idle_previews(cfg: dict[str, Any] | None = None) -> None:
    with _preview_lock:
        ids = list(_idle_previews.keys())
    for cam_id in ids:
        _stop_idle_preview(cam_id, cfg)


def _capture_writer(
    cam_id: str,
    proc: subprocess.Popen[bytes],
    out_f: Any,
    stop_event: threading.Event,
    stats: dict[str, Any] | None = None,
) -> None:
    """Write SSH MPEG-TS stdout to SSD; optionally tee chunks to a focus preview sink."""
    try:
        assert proc.stdout is not None
        while not stop_event.is_set():
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            out_f.write(chunk)
            if stats is not None:
                note_capture_bytes(stats, len(chunk))
            with _preview_lock:
                sink = _record_preview_sinks.get(cam_id)
            if sink is not None:
                # Bounded queue; drop oldest on pressure. Do NOT clear the whole
                # queue — that would tear annex-B mid-NAL until the next IDR.
                try:
                    sink.put_nowait(chunk)
                except queue.Full:
                    try:
                        sink.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        sink.put_nowait(chunk)
                    except queue.Full:
                        pass
    finally:
        try:
            out_f.flush()
            out_f.close()
        except Exception:
            pass
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass


def _stop_capture_entry(info: dict[str, Any]) -> None:
    stop_event = info.get("stop")
    if isinstance(stop_event, threading.Event):
        stop_event.set()
    proc = info.get("proc")
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
        except Exception:
            pass
    writer = info.get("writer")
    if isinstance(writer, threading.Thread) and writer.is_alive():
        writer.join(timeout=5)
    for fh in (info.get("stderr"),):
        try:
            if fh:
                fh.close()
        except Exception:
            pass


def start_cameras(meta: SubjectMeta, folder: Path, cfg: dict[str, Any]) -> list[str]:
    """Promote to science: cam ``rpicam | ffmpeg`` MPEG-TS over SSH.

    Cam keeps ``timestamps.pts`` (pulled at stop). NVR writes
    ``{subject}__{cam}__p000.ts``. Stdout teed for focus live (no NVR remux).
    """
    # Promote-on-start: kill idle preview before science encode.
    stop_all_idle_previews(cfg)
    by_id = {c["id"]: c for c in online_cameras(cfg)}
    op = load_operator_state(data_root())
    cam_metas = op.get("cameras") or {}
    log: list[str] = ["promote: stopped idle previews (if any); science wire=mpegts"]
    ask = science_encode_ask(meta.profile, meta.soft_fps, cfg)
    width, height = ask.width, ask.height
    soft_fps = ask.soft_fps
    bitrate_bps = ask.bitrate_bps
    intra = ask.intra
    buf = ask.buffer_count
    folder.mkdir(parents=True, exist_ok=True)

    for cam_id in meta.camera_ids:
        cam = by_id.get(cam_id)
        if not cam or not cam.get("online"):
            log.append(f"SKIP {cam_id} (not online in MQTT roster)")
            continue
        host = str(cam.get("ip") or "")
        if not host:
            log.append(f"SKIP {cam_id} (no ip)")
            continue
        cmeta = cam_metas.get(cam_id) or {}
        subject_id = str(cmeta.get("subject_id") or "").strip() or meta.subject_id
        stem = part_stem(subject_id, cam_id, 0)

        with _capture_lock:
            prev = _captures.pop(cam_id, None)
        if prev:
            _stop_capture_entry(prev)

        ts_path = folder / f"{stem}.ts"
        err_path = folder / f"{stem}_capture.log"
        pts_remote = f"{CAM_WORKDIR}/timestamps.pts"
        # soft_fps is an encoder request only — achieved rate is pts/fps.json.
        remote = cam_science_ssh_mpegts_remote(
            width=width,
            height=height,
            soft_fps=soft_fps,
            bitrate_bps=bitrate_bps,
            intra=intra,
            sensor_mode=ask.sensor_mode,
            buffer_count=buf,
            pts_remote=pts_remote,
            workdir=CAM_WORKDIR,
        )
        try:
            out_f = ts_path.open("wb")
            err_f = err_path.open("wb")
            proc = _popen_ssh_bash_s(
                cfg,
                host,
                remote,
                err_f=err_f,
                extra_ssh=[
                    "-o",
                    "ServerAliveInterval=10",
                    "-o",
                    "ServerAliveCountMax=3",
                ],
            )
        except OSError as exc:
            log.append(f"FAIL start {cam_id}@{host}: {exc}")
            continue

        stop_event = threading.Event()
        stats = new_capture_byte_stats()
        writer = threading.Thread(
            target=_capture_writer,
            args=(cam_id, proc, out_f, stop_event, stats),
            name=f"bhvr-cap-{cam_id}",
            daemon=True,
        )
        writer.start()

        time.sleep(2)
        if proc.poll() is not None:
            stop_event.set()
            writer.join(timeout=3)
            err_tail = ""
            try:
                err_tail = err_path.read_text(encoding="utf-8", errors="replace")[-500:]
            except OSError:
                pass
            log.append(
                f"FAIL start {cam_id}@{host}: exited rc={proc.returncode} {err_tail}"
            )
            try:
                err_f.close()
            except Exception:
                pass
            continue

        with _capture_lock:
            _captures[cam_id] = {
                "proc": proc,
                "stderr": err_f,
                "host": host,
                "video": str(ts_path),
                "h264": str(ts_path),  # legacy key — path is *.ts
                "stem": stem,
                "subject_id": subject_id,
                "part": 0,
                "stop": stop_event,
                "writer": writer,
                "stats": stats,
                "soft_fps": soft_fps,
                "bitrate_bps": bitrate_bps,
            }
        size = ts_path.stat().st_size if ts_path.is_file() else 0
        log.append(
            f"OK stream {cam_id}@{host} -> {ts_path.name} "
            f"pid={proc.pid} early_bytes={size} {meta.profile} "
            f"{width}x{height} soft_fps={soft_fps} bitrate_kbps={bitrate_bps // 1000}"
        )

    _save_capture_pids(folder)
    return log


def _fps_from_pts(pts_path: Path) -> dict[str, Any]:
    """Parse rpicam ``--save-pts`` text (ms). Tolerates corrupt/binary pulls."""
    lines: list[float] = []
    skipped = 0
    try:
        raw = pts_path.read_bytes()
    except OSError as exc:
        return {"pts_frames": 0, "achieved_fps": None, "error": str(exc)}
    # NUL-heavy or empty → not a usable text pts file
    if not raw or raw.count(0) > max(8, len(raw) // 4):
        return {
            "pts_frames": 0,
            "achieved_fps": None,
            "error": "pts_file_binary_or_empty",
            "bytes": len(raw),
        }
    text = raw.decode("utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # drop replacement chars / junk
        if "\x00" in line or "\ufffd" in line:
            skipped += 1
            continue
        try:
            lines.append(float(line))
        except ValueError:
            skipped += 1
            continue
    if len(lines) < 2:
        return {
            "pts_frames": len(lines),
            "achieved_fps": None,
            "skipped_lines": skipped,
        }
    # rpicam save-pts v2: milliseconds
    span_s = (lines[-1] - lines[0]) / 1000.0
    fps = (len(lines) - 1) / span_s if span_s > 0 else None
    dts = [lines[i + 1] - lines[i] for i in range(len(lines) - 1)]
    out: dict[str, Any] = {
        "pts_frames": len(lines),
        "span_s": round(span_s, 3),
        "achieved_fps": round(fps, 2) if fps is not None else None,
        "dt_ms_median": round(statistics.median(dts), 2),
        "dt_ms_p95": round(sorted(dts)[int(0.95 * (len(dts) - 1))], 2),
        "dt_ms_max": round(max(dts), 2),
    }
    if skipped:
        out["skipped_lines"] = skipped
    return out


def _remux_h264(src: Path, dest: Path, fps: int) -> tuple[int, str]:
    try:
        r = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(src),
                "-c",
                "copy",
                str(dest),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as exc:
        return 1, str(exc)
    if r.returncode != 0:
        return r.returncode, (r.stderr or r.stdout or "")[-400:]
    return 0, f"{dest.name} ({dest.stat().st_size} B)"


def stop_cameras(
    cfg: dict[str, Any],
    camera_ids: list[str],
    folder: Path | None = None,
    profile: str = "480p",
) -> list[str]:
    """Stop NVR SSH capture pipes; pull tiny pts; write fps.json (keep ``*_video.ts``)."""
    stop_all_idle_previews(cfg)
    user = cfg.get("ssh_user", "admin")
    by_id = {c["id"]: c for c in online_cameras(cfg)}
    with _roster_lock:
        for cam_id, row in _roster.items():
            by_id.setdefault(cam_id, {**row, "id": cam_id, "online": True})
    log: list[str] = []
    _ = PROFILE_GEOM.get(profile, (1280, 720))
    if folder is not None:
        folder.mkdir(parents=True, exist_ok=True)

    for cam_id in camera_ids:
        cam = by_id.get(cam_id)
        host = str((cam or {}).get("ip") or "")
        with _preview_lock:
            sink = _record_preview_sinks.pop(cam_id, None)
        if sink is not None:
            try:
                sink.put_nowait(None)
            except queue.Full:
                pass
        with _capture_lock:
            info = _captures.pop(cam_id, None)
        video = Path("")
        stem = ""
        if info and info.get("proc"):
            host = str(info.get("host") or host)
            stem = str(info.get("stem") or "")
            video = Path(str(info.get("video") or info.get("h264") or ""))
            _stop_capture_entry(info)
            nbytes = video.stat().st_size if video.is_file() else 0
            log.append(f"OK stop stream {cam_id} nvr_bytes={nbytes}")
        else:
            if host:
                _ssh_run(
                    cfg,
                    host,
                    "pkill -INT rpicam-vid 2>/dev/null || true; "
                    "pkill -x ffmpeg 2>/dev/null || true; sleep 1; "
                    "pkill -9 rpicam-vid 2>/dev/null || true",
                    timeout=30,
                )
            log.append(
                f"WARN stop {cam_id}: no local capture proc (killed remote if reachable)"
            )
            if folder is not None and not video.is_file():
                matches = sorted(folder.glob(f"*__{slug(cam_id)}__p*.ts"))
                if matches:
                    video = matches[-1]
                    stem = video.stem

        if folder is None or not host:
            continue

        if not video.is_file() and stem:
            video = folder / f"{stem}.ts"
        if not video.is_file():
            # Legacy name from pre-grill sessions.
            legacy = folder / f"{cam_id}_video.ts"
            if legacy.is_file():
                video = legacy
                stem = cam_id + "_video"
        dest_ts = video if video.is_file() else folder / f"{cam_id}_video.ts"
        dest_pts = (
            dest_ts.with_suffix(".pts")
            if dest_ts.suffix == ".ts"
            else folder / f"{cam_id}_timestamps.pts"
        )
        identity = cfg.get("ssh_identity_file") or ""
        rsync = ["rsync", "-avz", "--timeout=120"]
        if identity:
            rsync.extend(
                [
                    "-e",
                    f"ssh -i {identity} -o BatchMode=yes -o IdentitiesOnly=yes",
                ]
            )
        try:
            rr = subprocess.run(
                [*rsync, f"{user}@{host}:bhvr-current/timestamps.pts", str(dest_pts)],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            log.append(f"FAIL pull pts {cam_id}: {exc}")
            rr = None
        if rr is not None:
            if rr.returncode == 0 and dest_pts.is_file():
                log.append(f"OK pull pts {cam_id} ({dest_pts.stat().st_size} B)")
            else:
                err = (rr.stderr or rr.stdout or "").strip() or f"exit {rr.returncode}"
                log.append(f"FAIL pull pts {cam_id}: {err}")

        if dest_ts.is_file() and dest_ts.stat().st_size > 0:
            log.append(f"OK keep {dest_ts.name} ({dest_ts.stat().st_size} B)")
        else:
            log.append(f"FAIL archive {cam_id}: missing/empty {dest_ts.name}")

        if dest_pts.is_file():
            try:
                stats = _fps_from_pts(dest_pts)
                log.append(f"FPS {cam_id}: {json.dumps(stats)}")
                fps_path = (
                    dest_ts.with_name(dest_ts.stem + "_fps.json")
                    if dest_ts.suffix == ".ts"
                    else folder / f"{cam_id}_fps.json"
                )
                fps_path.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
            except Exception as exc:  # noqa: BLE001 — never block session stop
                log.append(f"FAIL fps parse {cam_id}: {exc}")

    if folder is not None and _capture_pid_path(folder).is_file():
        _capture_pid_path(folder).unlink(missing_ok=True)
    return log


def _cam_host(cfg: dict[str, Any], cam_id: str) -> str:
    by_id = {c["id"]: c for c in online_cameras(cfg)}
    with _roster_lock:
        for cid, row in _roster.items():
            by_id.setdefault(cid, {**row, "id": cid, "online": True})
    cam = by_id.get(cam_id)
    return str((cam or {}).get("ip") or "")


def _start_cam_udp_publish(
    cfg: dict[str, Any],
    cam_id: str,
    host: str,
    settings: Any,
    nvr_ip: str,
    port: int,
) -> tuple[subprocess.Popen[bytes] | None, Any]:
    err_path = Path(f"/tmp/bhvr-preview-{cam_id}-cam.log")
    err_f = err_path.open("wb")
    remote = cam_live_udp_remote(settings, nvr_ip, port)
    proc = subprocess.Popen(
        [*_ssh_argv(cfg, host), remote],
        stdout=subprocess.DEVNULL,
        stderr=err_f,
        stdin=subprocess.DEVNULL,
    )
    return proc, err_f


def _start_cam_annexb_nvr_remux(
    cfg: dict[str, Any],
    cam_id: str,
    host: str,
    settings: Any,
    port: int,
) -> tuple[subprocess.Popen[bytes] | None, Any, subprocess.Popen[bytes] | None, Any]:
    """O1a: SSH annex-B from cam → NVR ffmpeg → MPEG-TS UDP loopback for MediaMTX."""
    cam_err_path = Path(f"/tmp/bhvr-preview-{cam_id}-cam.log")
    ff_err_path = Path(f"/tmp/bhvr-preview-{cam_id}-remux.log")
    cam_err = cam_err_path.open("wb")
    ff_err = ff_err_path.open("wb")
    remote = cam_live_annexb_remote(settings)
    cam_proc = subprocess.Popen(
        [
            *_ssh_argv(cfg, host),
            "-o",
            "ServerAliveInterval=10",
            "-o",
            "ServerAliveCountMax=3",
            remote,
        ],
        stdout=subprocess.PIPE,
        stderr=cam_err,
        stdin=subprocess.DEVNULL,
        bufsize=0,
    )
    assert cam_proc.stdout is not None
    ff = subprocess.Popen(
        nvr_ffmpeg_annexb_to_mediamtx_udp(port),
        stdin=cam_proc.stdout,
        stdout=subprocess.DEVNULL,
        stderr=ff_err,
        bufsize=0,
    )
    # Allow cam_proc to receive SIGPIPE if remux dies.
    cam_proc.stdout.close()
    return cam_proc, cam_err, ff, ff_err


def _iter_idle_preview_udp(cfg: dict[str, Any], cam_id: str, host: str) -> Iterator[bytes]:
    """Cam MPEG-TS over UDP → NVR ffmpeg → browser mpegts.js.

    Bind NVR ffmpeg first (UDP ``timeout`` keeps it open), then start the cam so
    the first packets include SPS/PPS. Do not probe-consume UDP beforehand.
    """
    settings = live_preview_settings(cfg, cam_id=cam_id)
    nvr_ip = nvr_ingress_ip(cfg)
    port = cam_udp_port(cam_id, settings.udp_port)
    # Per-cam ports — do not stop other idle publishers (issue 12).
    _stop_idle_preview(cam_id, cfg)

    err_path = Path(f"/tmp/bhvr-preview-{cam_id}.log")
    err_f = err_path.open("wb")
    ff = subprocess.Popen(
        nvr_ffmpeg_udp_to_mpegts_pipe(port),
        stdout=subprocess.PIPE,
        stderr=err_f,
        stdin=subprocess.DEVNULL,
        bufsize=0,
    )
    time.sleep(0.4)  # let UDP socket bind before cam traffic
    cam_proc, cam_err = _start_cam_udp_publish(cfg, cam_id, host, settings, nvr_ip, port)
    stop = threading.Event()
    with _preview_lock:
        _idle_previews[cam_id] = {
            "ffmpeg": ff,
            "cam_proc": cam_proc,
            "stderr": err_f,
            "cam_stderr": cam_err,
            "host": host,
            "stop": stop,
            "udp": True,
        }

    assert ff.stdout is not None
    deadline = time.time() + 25.0
    first = b""
    while time.time() < deadline and not first:
        if ff.poll() is not None:
            break
        ready, _, _ = select.select([ff.stdout], [], [], 0.5)
        if not ready:
            continue
        chunk = ff.stdout.read(65536)
        if chunk:
            first = chunk
            break
    if not first:
        stop.set()
        _stop_idle_preview(cam_id, cfg)
        raise HTTPException(
            503,
            f"no UDP/TS from {cam_id}@{host} → {nvr_ip}:{port} (ffmpeg got nothing)",
        )
    yield first
    try:
        while not stop.is_set():
            chunk = ff.stdout.read(65536)
            if not chunk:
                break
            yield chunk
    finally:
        stop.set()
        _stop_idle_preview(cam_id, cfg)


def _iter_idle_preview_ssh_mpegts(cfg: dict[str, Any], cam_id: str, host: str) -> Iterator[bytes]:
    """SSH TCP: rpicam | ffmpeg MPEG-TS → browser (campus-WiFi friendly)."""
    settings = live_preview_settings(cfg, cam_id=cam_id)
    _stop_idle_preview(cam_id, cfg)

    err_path = Path(f"/tmp/bhvr-preview-{cam_id}.log")
    err_f = err_path.open("wb")
    ssh_proc = _popen_ssh_bash_s(
        cfg,
        host,
        cam_live_ssh_mpegts_remote(settings),
        err_f=err_f,
        extra_ssh=[
            "-o",
            "ServerAliveInterval=10",
            "-o",
            "ServerAliveCountMax=3",
        ],
    )
    stop = threading.Event()
    with _preview_lock:
        _idle_previews[cam_id] = {
            "proc": ssh_proc,
            "stderr": err_f,
            "host": host,
            "stop": stop,
            "udp": False,
        }
    try:
        assert ssh_proc.stdout is not None
        while not stop.is_set():
            chunk = ssh_proc.stdout.read(65536)
            if not chunk:
                break
            yield chunk
    finally:
        stop.set()
        _stop_idle_preview(cam_id, cfg)


def _iter_idle_preview(cfg: dict[str, Any], cam_id: str, host: str) -> Iterator[bytes]:
    """SSH HW H.264 annex-B straight to the browser (jmuxer / MSE)."""
    settings = live_preview_settings(cfg, cam_id=cam_id)
    _stop_idle_preview(cam_id, cfg)

    err_path = Path(f"/tmp/bhvr-preview-{cam_id}.log")
    err_f = err_path.open("wb")
    argv = [
        *_ssh_argv(cfg, host),
        "-o",
        "ServerAliveInterval=10",
        "-o",
        "ServerAliveCountMax=3",
        idle_rpicam_remote(settings),
    ]
    ssh_proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=err_f,
        stdin=subprocess.DEVNULL,
        bufsize=0,
    )
    stop = threading.Event()
    with _preview_lock:
        _idle_previews[cam_id] = {
            "proc": ssh_proc,
            "stderr": err_f,
            "host": host,
            "stop": stop,
        }
    try:
        assert ssh_proc.stdout is not None
        while not stop.is_set():
            chunk = ssh_proc.stdout.read(65536)
            if not chunk:
                break
            yield chunk
    finally:
        stop.set()
        _stop_idle_preview(cam_id, cfg)


def _iter_record_preview(cam_id: str, cfg: dict[str, Any]) -> Iterator[bytes]:
    """Stream science capture tee: same MPEG-TS bytes as ``*_video.ts`` (no NVR remux)."""
    _ = cfg
    with _capture_lock:
        if cam_id not in _captures:
            raise HTTPException(409, f"{cam_id} is not recording on this NVR")

    tee_max = preview_settings(cfg).tee_queue_max
    sink: queue.Queue[bytes | None] = queue.Queue(maxsize=tee_max)
    with _preview_lock:
        old = _record_preview_sinks.get(cam_id)
        _record_preview_sinks[cam_id] = sink
    if old is not None:
        try:
            old.put_nowait(None)
        except queue.Full:
            pass

    stop = threading.Event()
    print(
        f"rec-tee {cam_id}: mpegts byte-tee sink registered (queue_max={tee_max})",
        flush=True,
    )
    try:
        yield from feed_queue_to_iterator(sink, stop)
    finally:
        stop.set()
        try:
            sink.put_nowait(None)
        except queue.Full:
            pass
        with _preview_lock:
            if _record_preview_sinks.get(cam_id) is sink:
                _record_preview_sinks.pop(cam_id, None)


def _mqtt_loop() -> None:
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("paho-mqtt not installed; roster stays empty", flush=True)
        return

    cfg = load_config()
    mq = cfg.get("mqtt", {})
    host = mq.get("host", "127.0.0.1")
    port = int(mq.get("port", 1883))
    topic = mq.get("topic", "bhvr/cam/+/state")

    def on_message(_client: Any, _userdata: Any, msg: Any) -> None:
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        cam_id = str(data.get("id") or "").strip()
        ip = str(data.get("ip") or "").strip()
        if not cam_id or not ip:
            return
        temp_c = _coerce_float(data.get("temp_c"))
        rh_pct = _coerce_float(data.get("rh_pct"))
        env_stats = data.get("env") if isinstance(data.get("env"), dict) else None
        ts = data.get("ts")
        link_raw = str(data.get("link") or "").strip().lower()
        ips_raw = data.get("ips") if isinstance(data.get("ips"), dict) else None
        ips: dict[str, str] | None = None
        if ips_raw:
            ips = {
                str(k): str(v).strip()
                for k, v in ips_raw.items()
                if str(v).strip() and str(k) in ("usb", "wifi")
            } or None
        new_link = announce_link_mode(ip, link_raw or None)
        path_changed = False
        with _roster_lock:
            prev = _roster.get(cam_id) or {}
            prev_ip = str(prev.get("ip") or "")
            prev_link = str(prev.get("link") or "")
            path_changed = bool(prev) and (prev_ip != ip or prev_link != new_link)
            row: dict[str, Any] = {
                "ip": ip,
                "profile": data.get("profile"),
                "ts": ts,
                "seen_at": time.time(),
                "link": new_link,
            }
            if ips:
                row["ips"] = ips
            if temp_c is not None:
                row["temp_c"] = temp_c
            if rh_pct is not None:
                row["rh_pct"] = rh_pct
            if env_stats is not None:
                row["env"] = env_stats
            _roster[cam_id] = row
        # Drop idle WHEP publisher pinned to the old USB/WiFi SSH host.
        if path_changed:
            try:
                _stop_idle_preview(cam_id, cfg)
            except Exception:
                pass
        # REC archive: prefer window min/max/mean; else legacy scalar means.
        if env_stats is not None and isinstance(env_stats.get("temp_c"), dict):
            _maybe_append_env_jsonl(
                cam_id,
                ts=str(ts) if ts else None,
                env=env_stats,
            )
        elif temp_c is not None and rh_pct is not None:
            _maybe_append_env_jsonl(
                cam_id,
                ts=str(ts) if ts else None,
                temp_c=temp_c,
                rh_pct=rh_pct,
            )

    def on_connect(
        client: Any,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any = None,
    ) -> None:
        # Must (re)subscribe here — paho loop_forever auto-reconnects without
        # re-running the outer subscribe, which left weekend rosters frozen
        # while mosquitto still had fresh cam announces.
        rc = getattr(reason_code, "value", reason_code)
        print(f"mqtt connected host={host}:{port} rc={rc} sub={topic}", flush=True)
        client.subscribe(topic)

    def on_disconnect(
        _client: Any,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any = None,
    ) -> None:
        rc = getattr(reason_code, "value", reason_code)
        print(f"mqtt disconnected rc={rc}", flush=True)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    while True:
        try:
            client.connect(host, port, keepalive=60)
            client.loop_forever()
        except Exception as exc:  # noqa: BLE001 — keep thread alive
            print(f"mqtt reconnect in 5s: {exc}", flush=True)
            time.sleep(5)


@app.on_event("startup")
def _startup() -> None:
    global _mqtt_thread
    if _mqtt_thread and _mqtt_thread.is_alive():
        return
    _mqtt_thread = threading.Thread(target=_mqtt_loop, name="bhvr-mqtt", daemon=True)
    _mqtt_thread.start()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    cfg = load_config()
    active = None
    if active_path().is_file():
        active = json.loads(active_path().read_text(encoding="utf-8"))
    op = load_operator_state(data_root())
    cam_metas = op.get("cameras") or {}
    cams = online_cameras(cfg)
    for c in cams:
        c["animal"] = cam_metas.get(c["id"]) or {
            "subject_id": "",
            "cage_id": "",
            "sex": "U",
            "strain": "",
            "notes": "",
        }
    # Pad to 4 tiles for a stable 2x2 grid during wireless soak.
    tiles: list[dict[str, Any] | None] = list(cams[:4])
    while len(tiles) < 4:
        tiles.append(None)
    prev = live_preview_settings(cfg)
    ask = encode_ask(op["profile"], op["soft_fps"])
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {
            "cfg": cfg,
            "active": active,
            "profiles": list(SCIENCE_SIZE_IDS),
            "science_size_options": science_size_options(),
            "science_fps_options": list(SCIENCE_FPS_OPTIONS),
            "default_science_size": op["profile"],
            "default_science_fps": op["soft_fps"],
            "operator": op,
            "storage": storage_health(data_root()),
            "cameras": cams,
            "tiles": tiles,
            "data_root": str(data_root()),
            "preview_transport": prev.transport,
            "preview_width": prev.width,
            "preview_height": prev.height,
            "idle_ask_label": ask.label,
        },
    )


@app.get("/api/cams")
def api_cams() -> dict[str, Any]:
    cfg = load_config()
    cams = online_cameras(cfg)
    return {
        "cameras": cams,
        "science_size_options": science_size_options(),
        "science_fps_options": list(SCIENCE_FPS_OPTIONS),
    }


@app.get("/api/cams/{cam_id}/sensor-mode")
def api_get_sensor_mode(cam_id: str) -> dict[str, Any]:
    """Legacy read — mode is baked from science/idle ask (grill 11)."""
    cfg = load_config()
    cam_id = cam_id.strip()
    prev = preview_settings(cfg, cam_id=cam_id)
    return {
        "cam_id": cam_id,
        "sensor_mode": prev.sensor_mode,
        "deprecated": True,
        "hint": "Use session science ask (Standard/Lite × fps); sensor-mode PUT removed.",
        "options": [
            {"id": mid, "label": SENSOR_MODE_LABELS[mid]} for mid in SENSOR_MODE_IDS
        ],
    }


class SensorModeBody(BaseModel):
    sensor_mode: str = Field(min_length=1)


@app.put("/api/cams/{cam_id}/sensor-mode")
def api_put_sensor_mode(cam_id: str, body: SensorModeBody) -> JSONResponse:
    """Removed from operator UI (grill 11). Returns 410."""
    _ = (cam_id, body)
    raise HTTPException(
        410,
        "sensor-mode PUT removed; set Standard/Lite × fps in Start recording modal",
    )


class WebRtcOfferBody(BaseModel):
    sdp: str = Field(min_length=1)
    type: str = Field(default="offer")


@app.get("/api/preview/{cam_id}")
def api_preview(cam_id: str) -> StreamingResponse:
    """Focus live: MPEG-TS over HTTP (mpegts.js) or annex-B (legacy jmuxer)."""
    cfg = load_config()
    cam_id = cam_id.strip()
    if not cam_id:
        raise HTTPException(400, "cam_id required")
    settings = preview_settings(cfg)

    with _capture_lock:
        capturing = cam_id in _captures
    session_cams = _active_session_camera_ids()
    in_session = cam_id in session_cams

    # Science session owns the cam encode (MPEG-TS on SSH). Idle would pkill it —
    # only tee the science capture. Browser always uses MPEG-TS here (even if idle
    # transport is whep). Multi-cam tees OK (per-cam sink).
    if in_session or capturing:
        if in_session and not capturing:
            raise HTTPException(
                409,
                f"{cam_id} is in an active session but this kiosk process is not "
                "capturing it (web restarted?). Stop the session or restart capture — "
                "refusing live so we do not kill the cam encode.",
            )
        stop_all_idle_previews(cfg)
        gen = _iter_record_preview(cam_id, cfg)
        media_type = "video/mp2t"
    else:
        host = _cam_host(cfg, cam_id)
        if not host:
            raise HTTPException(404, f"{cam_id} not in MQTT roster / no ip")
        if settings.transport == "webrtc":
            raise HTTPException(400, "use POST /api/preview/{cam_id}/webrtc for WebRTC")
        if settings.transport == "whep":
            raise HTTPException(400, "use POST /api/preview/{cam_id}/whep/start for MediaMTX WHEP")
        if settings.transport == "mpegts":
            gen = _iter_idle_preview_ssh_mpegts(cfg, cam_id, host)
            media_type = "video/mp2t"
        elif settings.transport == "udp":
            gen = _iter_idle_preview_udp(cfg, cam_id, host)
            media_type = "video/mp2t"
        else:
            gen = _iter_idle_preview(cfg, cam_id, host)
            media_type = "application/octet-stream"

    return StreamingResponse(
        gen,
        media_type=media_type,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _start_idle_whep_publish(cfg: dict[str, Any], cam_id: str, host: str) -> dict[str, Any]:
    """Publish into MediaMTX ``15550+N``; browser reads WHEP.

    ``preview.whep_ingest``:
      - ``cam_mpegts`` (default): cam rpicam|ffmpeg MPEG-TS → UDP NVR
      - ``nvr_annexb`` (O1a): cam annex-B over SSH → NVR ffmpeg → UDP loopback

    Encode ask follows Session settings (``live_preview_settings``), not the
    baked Lite@10 ``idle_encode_ask`` used only as preview.yaml fallbacks.
    """
    settings = live_preview_settings(cfg, cam_id=cam_id)
    nvr_ip = nvr_ingress_ip(cfg)
    port = cam_udp_port(cam_id, settings.udp_port)
    # Per-cam ports — concurrent idle publishers OK (issue 12); only restart this cam.
    _stop_idle_preview(cam_id, cfg)

    stop = threading.Event()
    ingest = settings.whep_ingest
    if ingest == "nvr_annexb":
        cam_proc, cam_err, ff, ff_err = _start_cam_annexb_nvr_remux(
            cfg, cam_id, host, settings, port
        )
        with _preview_lock:
            _idle_previews[cam_id] = {
                "cam_proc": cam_proc,
                "cam_stderr": cam_err,
                "ffmpeg": ff,
                "stderr": ff_err,
                "host": host,
                "stop": stop,
                "annexb": True,
                "whep": True,
                "udp_port": port,
                "whep_ingest": ingest,
            }
    else:
        cam_proc, cam_err = _start_cam_udp_publish(cfg, cam_id, host, settings, nvr_ip, port)
        with _preview_lock:
            _idle_previews[cam_id] = {
                "cam_proc": cam_proc,
                "cam_stderr": cam_err,
                "host": host,
                "stop": stop,
                "udp": True,
                "whep": True,
                "udp_port": port,
                "whep_ingest": ingest,
            }
    return {
        "cam_id": cam_id,
        "whep_url": mediamtx_whep_url(settings, cam_id),
        "nvr_ip": nvr_ip,
        "udp_port": port,
        "path": cam_id,
        "sensor_mode": settings.sensor_mode,
        "whep_ingest": ingest,
    }


@app.post("/api/preview/{cam_id}/whep/start")
def api_preview_whep_start(cam_id: str) -> JSONResponse:
    """Start cam UDP publish into MediaMTX; return WHEP URL for the browser reader."""
    cfg = load_config()
    cam_id = cam_id.strip()
    if not cam_id:
        raise HTTPException(400, "cam_id required")
    settings = preview_settings(cfg)
    if settings.transport != "whep":
        raise HTTPException(400, "preview.transport is not whep")

    with _capture_lock:
        recording = cam_id in _captures
    if recording or cam_id in _active_session_camera_ids():
        raise HTTPException(
            409,
            "WHEP focus is idle-only while a science session owns the cam",
        )

    host, litmus_detail = _resolve_reachable_cam_host(cfg, cam_id)
    if not host:
        raise HTTPException(
            503,
            f"no SSH path to {cam_id} (online≠LIVE). "
            f"Re-check roster ip/ips, or plug USB. detail={litmus_detail}",
        )

    # annexb remote already pkills; only pre-free when we already had an idle
    # publisher (avoids double SSH+sleep on a cold tap → long black tile).
    with _preview_lock:
        had_idle = cam_id in _idle_previews
    if had_idle:
        _free_cam_encode_hosts(cfg, cam_id, [host])
    info = _start_idle_whep_publish(cfg, cam_id, host)
    info["ssh_host"] = host
    info["ssh_litmus"] = litmus_detail
    # Poll for a live remux instead of a fixed 3–5s sleep (that was most of the
    # black frame before the browser even started WHEP).
    settle_budget = 4.0 if not host.startswith("192.168.7.") else 2.5

    def _publish_dead() -> bool:
        with _preview_lock:
            entry = _idle_previews.get(cam_id) or {}
            alive = cam_id in _idle_previews
            cam_proc = entry.get("cam_proc")
            remux = entry.get("ffmpeg")
        cam_dead = cam_proc is not None and cam_proc.poll() is not None
        remux_dead = remux is not None and remux.poll() is not None
        return (not alive) or cam_dead or remux_dead

    def _wait_publish_up(budget_s: float) -> bool:
        deadline = time.monotonic() + budget_s
        # Give SSH/rpicam a beat before the first poll.
        time.sleep(0.4)
        while time.monotonic() < deadline:
            if not _publish_dead():
                return True
            time.sleep(0.15)
        return not _publish_dead()

    if not _wait_publish_up(settle_budget):
        # One retry — first attempt often loses the remux probe race.
        _stop_idle_preview(cam_id, cfg)
        time.sleep(0.3)
        info = _start_idle_whep_publish(cfg, cam_id, host)
        info["ssh_host"] = host
        info["ssh_litmus"] = litmus_detail
        if not _wait_publish_up(settle_budget):
            _stop_idle_preview(cam_id, cfg)
            raise HTTPException(
                503,
                f"WHEP publish died for {cam_id} via {host} "
                f"(cam_log=/tmp/bhvr-preview-{cam_id}-cam.log "
                f"remux_log=/tmp/bhvr-preview-{cam_id}-remux.log)",
            )
    return JSONResponse(info)


@app.post("/api/preview/{cam_id}/webrtc")
async def api_preview_webrtc(cam_id: str, body: WebRtcOfferBody) -> JSONResponse:
    """WebRTC answer: cam UDP MPEG-TS → aiortc MediaPlayer on NVR."""
    cfg = load_config()
    cam_id = cam_id.strip()
    settings = preview_settings(cfg)
    if settings.transport != "webrtc":
        raise HTTPException(400, "preview.transport is not webrtc")

    with _capture_lock:
        recording = cam_id in _captures
    if recording:
        raise HTTPException(501, "WebRTC while recording not implemented — use mpegts transport")

    host = _cam_host(cfg, cam_id)
    if not host:
        raise HTTPException(404, f"{cam_id} not in MQTT roster / no ip")

    # Legacy aiortc path still exclusive (single MediaPlayer); whep/udp are multi-cam.
    stop_all_idle_previews(cfg)
    await webrtc_preview.close_all_webrtc_previews()

    nvr_ip = nvr_ingress_ip(cfg)
    port = cam_udp_port(cam_id, settings.udp_port)
    # Do not probe-consume UDP before MediaPlayer — that ate SPS/PPS and blacked the tile.
    # Start publish, then let MediaPlayer bind; --inline + frequent intra re-sends headers.
    cam_proc, cam_err = _start_cam_udp_publish(cfg, cam_id, host, settings, nvr_ip, port)
    stop = threading.Event()
    with _preview_lock:
        _idle_previews[cam_id] = {
            "cam_proc": cam_proc,
            "cam_stderr": cam_err,
            "host": host,
            "stop": stop,
            "udp": True,
        }

    try:
        answer = await webrtc_preview.handle_webrtc_offer(
            cam_id,
            body.sdp,
            body.type,
            settings,
            port,
        )
    except Exception as exc:
        _stop_idle_preview(cam_id, cfg)
        raise HTTPException(503, f"WebRTC setup failed: {exc}") from exc

    return JSONResponse(
        {"sdp": answer.sdp, "type": answer.type},
    )


@app.post("/api/preview/stop")
async def api_preview_stop(cam_id: str | None = Query(default=None)) -> dict[str, Any]:
    cfg = load_config()
    if cam_id:
        await webrtc_preview.close_webrtc_preview(cam_id.strip())
        await asyncio.to_thread(_stop_idle_preview, cam_id, cfg)
        with _preview_lock:
            q = _record_preview_sinks.pop(cam_id, None)
        if q is not None:
            try:
                q.put_nowait(None)
            except queue.Full:
                pass
    else:
        await webrtc_preview.close_all_webrtc_previews()
        await asyncio.to_thread(stop_all_idle_previews, cfg)
        with _preview_lock:
            sinks = list(_record_preview_sinks.items())
            _record_preview_sinks.clear()
        for _cid, q in sinks:
            try:
                q.put_nowait(None)
            except queue.Full:
                pass
    return {"status": "stopped", "cam_id": cam_id}


def _beacon_burst(seconds: float = 45.0, interval: float = 2.0) -> None:
    """On-demand broker invite — not a continuous spam loop."""
    bin_path = Path("/usr/local/bin/bhvr-broker-beacon")
    cmd = (
        [str(bin_path), "--once"]
        if bin_path.is_file()
        else [
            "python3",
            str(ROOT.parent / "bhvr-nvr" / "scripts" / "broker_beacon.py"),
            "--once",
        ]
    )
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            subprocess.run(cmd, check=False, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"beacon failed: {exc}", flush=True)
            return
        time.sleep(interval)


@app.post("/api/beacon")
def api_beacon() -> JSONResponse:
    """Kiosk 'Invite cameras' — burst UDP beacons for ~45s."""
    threading.Thread(target=_beacon_burst, name="bhvr-beacon-burst", daemon=True).start()
    return JSONResponse(
        {
            "status": "burst_started",
            "seconds": 45,
            "hint": "cams listening will cache broker & announce",
        }
    )


@app.post("/beacon")
def beacon_form() -> RedirectResponse:
    api_beacon()
    return RedirectResponse("/", status_code=303)


def _begin_session(meta: SubjectMeta, cfg: dict[str, Any]) -> dict[str, Any]:
    if active_path().is_file():
        raise HTTPException(409, "session already active; stop first")
    health = storage_health(data_root())
    if not health.get("mounted"):
        raise HTTPException(
            503,
            f"data_root not mounted/writable: {health.get('data_root')}",
        )
    op = load_operator_state(data_root())
    # Science knobs come from Session settings (operator state), not Start form.
    size = normalize_science_size(op.get("profile"))
    meta.profile = size
    meta.soft_fps = normalize_soft_fps(op.get("soft_fps"))
    allowed = set(cfg.get("profiles") or list(SCIENCE_SIZE_IDS))
    if allowed and size not in allowed and meta.profile not in PROFILE_GEOM:
        legacy_ok = any(normalize_science_size(p) == size for p in allowed)
        if not legacy_ok and size not in SCIENCE_SIZE_IDS:
            raise HTTPException(400, f"profile {meta.profile} not enabled in config")
    if not meta.camera_ids:
        raise HTTPException(400, "select at least one camera")
    cams_meta = op.get("cameras") or {}
    missing = [
        cid
        for cid in meta.camera_ids
        if not str((cams_meta.get(cid) or {}).get("subject_id") or "").strip()
    ]
    if missing:
        raise HTTPException(
            400,
            "set subject_id on each camera first (Cam metadata): " + ", ".join(missing),
        )
    # Legacy session meta still wants one subject_id; use first cam's.
    first = str((cams_meta.get(meta.camera_ids[0]) or {}).get("subject_id") or "").strip()
    meta.subject_id = first or meta.subject_id
    ask = science_encode_ask(meta.profile, meta.soft_fps, cfg)
    start = datetime.now(timezone.utc)
    folder = session_dir(meta, start)
    folder.mkdir(parents=True, exist_ok=True)
    # No session meta.json (grill Q16=B′); runtime state stays in .active_session.json.
    cam_log = start_cameras(meta, folder, cfg)
    active_path().parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "folder": str(folder),
        "started": start.isoformat(),
        "meta": {
            **meta.model_dump(),
            "science_ask": ask.label,
            "chunk_minutes": int(op.get("chunk_minutes") or 0),
            "output_subdir": op.get("output_subdir") or "",
            "cameras": {
                cid: dict(cams_meta.get(cid) or {}) for cid in meta.camera_ids
            },
        },
        "cam_log": cam_log,
        "h5_pack": "stub",  # chunk roll + background H5 pack — next slice
    }
    active_path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _end_session() -> dict[str, Any]:
    if not active_path().is_file():
        raise HTTPException(404, "no active session")
    cfg = load_config()
    active = json.loads(active_path().read_text(encoding="utf-8"))
    camera_ids = active.get("meta", {}).get("camera_ids", [])
    profile = active.get("meta", {}).get("profile", "480p")
    folder_s = active.get("folder")
    folder = Path(folder_s) if folder_s else None
    try:
        stop_log = stop_cameras(cfg, camera_ids, folder=folder, profile=profile)
    except Exception as exc:  # noqa: BLE001 — always clear active session
        stop_log = [f"FAIL stop_cameras: {exc!r}"]
        print(f"_end_session stop_cameras error: {exc!r}", flush=True)
    if folder is not None:
        try:
            (folder / "stop_log.json").write_text(
                json.dumps(stop_log, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            stop_log.append(f"FAIL write stop_log: {exc}")
    active_path().unlink(missing_ok=True)
    return {"status": "stopped", "stop_log": stop_log, "folder": folder_s}


class SessionStartBody(BaseModel):
    """Start = cam checklist only; science knobs + subjects live in operator state."""

    camera_ids: list[str] = Field(default_factory=list)


class OperatorSettingsBody(BaseModel):
    profile: str | None = None
    soft_fps: int | None = None
    output_subdir: str | None = None
    chunk_minutes: int | None = None


class CamMetaBody(BaseModel):
    subject_id: str | None = None
    cage_id: str | None = None
    sex: str | None = Field(default=None, pattern=r"^[MFU]$")
    strain: str | None = None
    notes: str | None = None


@app.get("/api/session")
def api_session() -> dict[str, Any]:
    if not active_path().is_file():
        return {"active": None}
    return {"active": json.loads(active_path().read_text(encoding="utf-8"))}


@app.get("/api/operator/settings")
def api_operator_settings_get() -> dict[str, Any]:
    root = data_root()
    st = load_operator_state(root)
    health = storage_health(root)
    n_online = sum(1 for c in online_cameras(load_config()) if c.get("online"))
    est = estimate_gb_per_hour(st["profile"], st["soft_fps"], max(1, n_online))
    ask = encode_ask(st["profile"], st["soft_fps"])
    return {
        "settings": st,
        "storage": health,
        "subdirs": list_output_subdirs(root),
        "estimate": est,
        "science_ask": ask.label,
        "chunk_presets": {
            "lite": CHUNK_DEFAULT_LITE_MIN,
            "standard": CHUNK_DEFAULT_STANDARD_MIN,
            "for_profile": chunk_preset_minutes(st["profile"]),
        },
        "recording": active_path().is_file(),
        "science_size_options": science_size_options(),
        "science_fps_options": list(SCIENCE_FPS_OPTIONS),
    }


@app.put("/api/operator/settings")
def api_operator_settings_put(body: OperatorSettingsBody) -> JSONResponse:
    if active_path().is_file():
        # Size/fps locked while REC; allow only output_subdir? Grill: locked. Reject all.
        raise HTTPException(409, "stop recording before changing session settings")
    root = data_root()
    health = storage_health(root)
    if not health.get("mounted"):
        raise HTTPException(
            503,
            f"data_root not mounted/writable: {health.get('data_root')}",
        )
    cur = load_operator_state(root)
    patch = body.model_dump(exclude_unset=True)
    cur.update(patch)
    try:
        saved = save_operator_state(root, cur)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    # Idle live must restart to pick up new encode ask (grill Q10=A).
    stop_all_idle_previews(load_config())
    ask = encode_ask(saved["profile"], saved["soft_fps"])
    return JSONResponse(
        {
            "settings": saved,
            "science_ask": ask.label,
            "storage": health,
            "restart_idle": True,
        }
    )


@app.get("/api/cams/{cam_id}/meta")
def api_cam_meta_get(cam_id: str) -> dict[str, Any]:
    st = load_operator_state(data_root())
    return {
        "cam_id": cam_id,
        "meta": (st.get("cameras") or {}).get(cam_id)
        or {
            "subject_id": "",
            "cage_id": "",
            "sex": "U",
            "strain": "",
            "notes": "",
        },
        "subject_frozen": cam_id in _active_session_camera_ids(),
    }


@app.put("/api/cams/{cam_id}/meta")
def api_cam_meta_put(cam_id: str, body: CamMetaBody) -> JSONResponse:
    freeze = cam_id in _active_session_camera_ids()
    patch = body.model_dump(exclude_unset=True)
    if freeze and "subject_id" in patch:
        patch.pop("subject_id", None)
    meta = patch_cam_meta(data_root(), cam_id, patch, freeze_subject=freeze)
    return JSONResponse(
        {"cam_id": cam_id, "meta": meta, "subject_frozen": freeze}
    )


@app.get("/api/session/capture-stats")
def api_session_capture_stats() -> dict[str, Any]:
    """Per-cam SSD write health while recording (REC badge; independent of LIVE fps)."""
    with _capture_lock:
        items = [(cid, dict(info)) for cid, info in _captures.items()]
    cameras: dict[str, Any] = {}
    for cam_id, info in items:
        stats = info.get("stats")
        if not isinstance(stats, dict):
            stats = new_capture_byte_stats()
        snap = snapshot_capture_stats(
            stats,
            soft_fps=info.get("soft_fps"),
            bitrate_bps=info.get("bitrate_bps"),
        )
        snap["capturing"] = True
        cameras[cam_id] = snap
    return {
        "active": active_path().is_file(),
        "cameras": cameras,
    }


@app.post("/api/session/start")
def api_session_start(body: SessionStartBody) -> JSONResponse:
    cfg = load_config()
    op = load_operator_state(data_root())
    cams = body.camera_ids
    if not cams:
        raise HTTPException(400, "select at least one camera")
    first_meta = (op.get("cameras") or {}).get(cams[0]) or {}
    meta = SubjectMeta(
        subject_id=str(first_meta.get("subject_id") or "pending"),
        sex=str(first_meta.get("sex") or "U"),
        strain=str(first_meta.get("strain") or ""),
        cage_id=str(first_meta.get("cage_id") or ""),
        notes=str(first_meta.get("notes") or ""),
        profile=op.get("profile") or DEFAULT_SCIENCE_SIZE,
        soft_fps=int(op.get("soft_fps") or DEFAULT_SCIENCE_FPS),
        camera_ids=cams,
    )
    payload = _begin_session(meta, cfg)
    return JSONResponse(payload)


@app.post("/api/session/stop")
def api_session_stop() -> JSONResponse:
    return JSONResponse(_end_session())


@app.post("/session/start")
def session_start(
    camera_ids: list[str] = Form(default=[]),
) -> RedirectResponse:
    cfg = load_config()
    op = load_operator_state(data_root())
    if not camera_ids:
        raise HTTPException(400, "select at least one camera")
    first_meta = (op.get("cameras") or {}).get(camera_ids[0]) or {}
    meta = SubjectMeta(
        subject_id=str(first_meta.get("subject_id") or "pending"),
        sex=str(first_meta.get("sex") or "U"),
        strain=str(first_meta.get("strain") or ""),
        cage_id=str(first_meta.get("cage_id") or ""),
        notes=str(first_meta.get("notes") or ""),
        profile=op.get("profile") or DEFAULT_SCIENCE_SIZE,
        soft_fps=int(op.get("soft_fps") or DEFAULT_SCIENCE_FPS),
        camera_ids=camera_ids,
    )
    _begin_session(meta, cfg)
    return RedirectResponse("/", status_code=303)


@app.post("/session/stop")
def session_stop() -> RedirectResponse:
    _end_session()
    return RedirectResponse("/", status_code=303)


# --- Kiosk settings (fleet ops; SETTINGS_GRILL.md 2026-10-23) -----------------


class UsbPushBody(BaseModel):
    cam_ids: list[str] = Field(default_factory=list)


class WifiApplyBody(BaseModel):
    ssid: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    hidden: bool = False
    apply_nvr: bool = True


class BackupBody(BaseModel):
    unc: str = Field(min_length=3)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    sessions: list[str] = Field(default_factory=list)


class DataRootBody(BaseModel):
    data_root: str = Field(min_length=1)
    restart: bool = True


@app.get("/api/kiosk/status")
def api_kiosk_status() -> dict[str, Any]:
    cfg = load_config()
    root = kiosk_settings.openethomaze_root(cfg)
    tree = kiosk_settings.cam_tree(cfg)
    git = kiosk_settings.git_status(root)
    files = kiosk_settings.soft_bundle_files(tree)
    present = sum(1 for f in files if f["present"])
    health = storage_health(data_root())

    def _ssh_ok(ip: str) -> bool:
        ok, _ = _ssh_litmus(cfg, ip, attempts=1)
        return ok

    cams = kiosk_settings.eligible_usb_cams(online_cameras(cfg), ssh_ok=_ssh_ok)
    return {
        "git": git,
        "cam_tree": str(tree),
        "soft_files": files,
        "soft_present": present,
        "soft_total": len(files),
        "eligible": cams,
        "storage": health,
        "data_root": str(data_root()),
        "config_path": str(CONFIG_PATH if CONFIG_PATH.is_file() else EXAMPLE_PATH),
        "wifi_env": str(kiosk_settings.WIFI_ENV_PATH),
        "wifi_env_exists": kiosk_settings.WIFI_ENV_PATH.is_file(),
    }


@app.post("/api/kiosk/usb-push")
def api_kiosk_usb_push(body: UsbPushBody) -> JSONResponse:
    """Push soft fleet set to selected ONLINE·USB cams (grill § USB push)."""
    cfg = load_config()
    tree = kiosk_settings.cam_tree(cfg)
    if not tree.is_dir():
        raise HTTPException(400, f"cam tree missing: {tree}")

    def _ssh_ok(ip: str) -> bool:
        ok, _ = _ssh_litmus(cfg, ip, attempts=1)
        return ok

    eligible = {
        c["id"]: c
        for c in kiosk_settings.eligible_usb_cams(online_cameras(cfg), ssh_ok=_ssh_ok)
        if c.get("eligible")
    }
    want = [x.strip() for x in body.cam_ids if str(x).strip()]
    if not want:
        want = sorted(eligible.keys())
    results: list[dict[str, Any]] = []
    for cid in want:
        row = eligible.get(cid)
        if not row:
            results.append(
                {
                    "id": cid,
                    "ip": "",
                    "ok": False,
                    "log": ["not eligible (need ONLINE·USB + SSH litmus)"],
                }
            )
            continue
        results.append(
            kiosk_settings.push_soft_set_to_cam(
                cfg, cam_id=cid, host=row["ip"], tree=tree
            )
        )
    ok_n = sum(1 for r in results if r.get("ok"))
    return JSONResponse(
        {
            "ok": ok_n == len(results) and bool(results),
            "pushed": ok_n,
            "total": len(results),
            "git": kiosk_settings.git_status(kiosk_settings.openethomaze_root(cfg)),
            "results": results,
        }
    )


@app.post("/api/kiosk/wifi")
def api_kiosk_wifi(body: WifiApplyBody) -> JSONResponse:
    """Write-only Wi‑Fi apply: cams first (USB), NVR last (grill Q9=A)."""
    cfg = load_config()
    ssid = body.ssid.strip()
    password = body.password
    log: list[str] = []
    cam_results: list[dict[str, Any]] = []

    def _ssh_ok(ip: str) -> bool:
        ok, _ = _ssh_litmus(cfg, ip, attempts=1)
        return ok

    cams = [
        c
        for c in kiosk_settings.eligible_usb_cams(online_cameras(cfg), ssh_ok=_ssh_ok)
        if c.get("eligible")
    ]
    for c in cams:
        ok, detail = kiosk_settings.push_wifi_to_cam(
            cfg,
            host=c["ip"],
            ssid=ssid,
            password=password,
            hidden=body.hidden,
        )
        cam_results.append({"id": c["id"], "ip": c["ip"], "ok": ok, "detail": detail})
        log.append(f"{c['id']}: {'OK' if ok else 'FAIL'} — {detail}")

    env_ok, env_detail = kiosk_settings.write_wifi_env(
        ssid, password, hidden=body.hidden
    )
    log.append(f"wifi.env: {'OK' if env_ok else 'FAIL'} — {env_detail}")

    nvr_ok = True
    nvr_detail = "skipped"
    if body.apply_nvr:
        nvr_ok, nvr_detail = kiosk_settings.nmcli_wifi_apply_local(
            ssid, password, hidden=body.hidden
        )
        log.append(f"NVR: {'OK' if nvr_ok else 'FAIL'} — {nvr_detail}")

    all_cams = all(r["ok"] for r in cam_results) if cam_results else True
    return JSONResponse(
        {
            "ok": all_cams and env_ok and nvr_ok,
            "cams": cam_results,
            "nvr": {"ok": nvr_ok, "detail": nvr_detail},
            "wifi_env": {"ok": env_ok, "path": env_detail if env_ok else None},
            "log": log,
            "hint": "PSK never returned; re-enter to change again.",
        }
    )


@app.get("/api/kiosk/sessions")
def api_kiosk_sessions() -> dict[str, Any]:
    rows = kiosk_settings.list_session_folders(data_root())
    return {"sessions": rows, "data_root": str(data_root())}


@app.post("/api/kiosk/backup")
def api_kiosk_backup(body: BackupBody) -> JSONResponse:
    if not body.sessions:
        raise HTTPException(400, "select at least one session")
    # Resolve names → absolute paths under data_root
    catalog = {r["name"]: r["path"] for r in kiosk_settings.list_session_folders(data_root())}
    paths: list[str] = []
    for name in body.sessions:
        p = catalog.get(name) or name
        paths.append(p)
    result = kiosk_settings.backup_sessions_cifs(
        unc=body.unc,
        username=body.username,
        password=body.password,
        session_paths=paths,
    )
    return JSONResponse(result)


@app.put("/api/kiosk/data-root")
def api_kiosk_data_root(body: DataRootBody) -> JSONResponse:
    """Update data_root in config.yaml; optional kiosk web restart (grill Q20=A)."""
    if active_path().is_file():
        raise HTTPException(409, "stop recording before changing data_root")
    new_root = str(Path(body.data_root.strip()).expanduser())
    cfg = load_config()
    old = cfg.get("data_root")
    cfg["data_root"] = new_root
    save_config(cfg)
    restart: dict[str, Any] = {"attempted": False}
    if body.restart:
        ok, detail = kiosk_settings.restart_kiosk_web()
        restart = {"attempted": True, "ok": ok, "detail": detail}
    return JSONResponse(
        {
            "ok": True,
            "old": old,
            "new": new_root,
            "config": str(CONFIG_PATH),
            "restart": restart,
            "storage": storage_health(Path(new_root)),
        }
    )


@app.get("/api/health")
def health() -> dict[str, Any]:
    with _roster_lock:
        n = len(_roster)
    with _capture_lock:
        capturing = sorted(_captures.keys())
    with _preview_lock:
        idle_prev = sorted(_idle_previews.keys())
        rec_prev = sorted(_record_preview_sinks.keys())
    active = None
    if active_path().is_file():
        try:
            active = json.loads(active_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            active = {"error": "unreadable"}
    return {
        "status": "ok",
        "roster_size": n,
        "data_root": str(data_root()),
        "active": active is not None,
        "session": active,
        "capturing": capturing,
        "preview_idle": idle_prev,
        "preview_record": rec_prev,
        "preview_transport": preview_settings(load_config()).transport,
        "webrtc": webrtc_preview.webrtc_status(),
    }


@app.post("/api/diag/live-player")
def api_diag_live_player_post(body: LivePlayerSample) -> dict[str, Any]:
    """Browser posts buffered-ahead / fps while mpegts live (player-knob litmus)."""
    sample = {
        "t": time.time(),
        "cam_id": body.cam_id.strip(),
        "chase": bool(body.chase),
        "stash": int(body.stash),
        "paint_n": int(body.paint_n),
        "buffered_s": body.buffered_s,
        "stream_fps": body.stream_fps,
        "ts_ms": body.ts_ms,
    }
    with _live_player_lock:
        _live_player_samples.append(sample)
        n = len(_live_player_samples)
    return {"ok": True, "n": n}


@app.get("/api/diag/live-player")
def api_diag_live_player_get(
    chase: bool | None = None,
    stash: int | None = None,
    since_s: float = 30.0,
) -> dict[str, Any]:
    """Recent client samples; optional filter by chase/stash for litmus rungs."""
    now = time.time()
    cutoff = now - max(0.5, float(since_s))
    with _live_player_lock:
        rows = [r for r in _live_player_samples if float(r.get("t") or 0) >= cutoff]
    if chase is not None:
        rows = [r for r in rows if bool(r.get("chase")) is bool(chase)]
    if stash is not None:
        rows = [r for r in rows if int(r.get("stash") or -1) == int(stash)]
    bufs = [float(r["buffered_s"]) for r in rows if r.get("buffered_s") is not None]
    fpss = [float(r["stream_fps"]) for r in rows if r.get("stream_fps") is not None]

    def _stat(vals: list[float]) -> dict[str, float | None]:
        if not vals:
            return {"min": None, "med": None, "max": None, "n": 0}
        s = sorted(vals)
        return {
            "min": round(s[0], 3),
            "med": round(s[len(s) // 2], 3),
            "max": round(s[-1], 3),
            "n": len(s),
        }

    return {
        "n": len(rows),
        "buffered_s": _stat(bufs),
        "stream_fps": _stat(fpss),
        "samples": rows[-40:],
    }


@app.delete("/api/diag/live-player")
def api_diag_live_player_clear() -> dict[str, Any]:
    with _live_player_lock:
        _live_player_samples.clear()
    return {"ok": True, "n": 0}
