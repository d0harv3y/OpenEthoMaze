"""Live preview: cam HW H.264 → UDP MPEG-TS → NVR → browser (WebRTC or mpegts.js).

Legacy ``ssh_annex_b`` keeps annex-B over SSH + jmuxer (choppy on Zero W WiFi).
"""

from __future__ import annotations

import queue
import re
import socket
import threading
from dataclasses import dataclass
from typing import Any, Literal

from app.encode_ask import idle_encode_ask

PreviewTransport = Literal["webrtc", "mpegts", "udp", "ssh_annex_b", "whep"]
# How WHEP gets bytes into MediaMTX (issue 12 / O1a).
# cam_mpegts: rpicam|ffmpeg MPEG-TS on cam → UDP :15550+N (legacy).
# nvr_annexb: rpicam annex-B over SSH → NVR ffmpeg → UDP 127.0.0.1:15550+N.
WhepIngest = Literal["cam_mpegts", "nvr_annexb"]

# OV5647 / Pi Camera v1-class allowlist (libcamera --mode W:H:bit:P).
# Operator UI no longer exposes these (grill 11); kept for normalize/legacy API.
SensorModeId = Literal["auto", "1296:972", "1920:1080", "640:480"]
SENSOR_MODE_IDS: tuple[str, ...] = ("auto", "1296:972", "1920:1080", "640:480")
SENSOR_MODE_LABELS: dict[str, str] = {
    "auto": "Auto (libcamera)",
    "1296:972": "1296×972 binned (mode 4)",
    "1920:1080": "1920×1080 crop (legacy)",
    "640:480": "640×480 binned",
}


@dataclass(frozen=True)
class PreviewSettings:
    width: int = 640
    height: int = 480
    fps_idle: int = 15
    fps_record: int = 10
    bitrate_kbps: int = 800
    buffer_count: int = 1
    transport: PreviewTransport = "mpegts"
    udp_port: int = 15550
    nvr_host: str = ""
    # Browser → MediaMTX WHEP base (kiosk Chromium on NVR → localhost).
    mediamtx_http: str = "http://127.0.0.1:8889"
    sensor_mode: str = "auto"
    whep_ingest: WhepIngest = "cam_mpegts"
    # Record live tee: chunks buffered between capture writer and HTTP consumer.
    # Larger = absorbs short browser stalls (fewer mid-GOP drops); more RAM + lag
    # if chronically behind. Chunks are up to 64 KiB (see _capture_writer).
    tee_queue_max: int = 512


def normalize_sensor_mode(raw: str | None) -> str:
    mode = str(raw or "auto").strip().lower().replace("x", ":")
    if mode in ("", "default", "libcamera"):
        return "auto"
    if mode not in SENSOR_MODE_IDS:
        return "auto"
    return mode


def cam_sensor_mode(cfg: dict[str, Any] | None, cam_id: str) -> str:
    """Per-cam sensor mode (preview + science encode). Falls back to preview.sensor_mode."""
    cams = (cfg or {}).get("cam_sensor_mode") or {}
    if isinstance(cams, dict) and cam_id in cams:
        return normalize_sensor_mode(str(cams.get(cam_id)))
    raw = ((cfg or {}).get("preview") or {}).get("sensor_mode")
    return normalize_sensor_mode(str(raw) if raw is not None else "auto")


def rpicam_mode_flag(mode: str) -> str:
    """CLI fragment for rpicam-vid, including leading space, or empty for auto."""
    mode = normalize_sensor_mode(mode)
    if mode == "auto":
        return ""
    return f" --mode {mode}:10:P"


def preview_settings(
    cfg: dict[str, Any] | None, *, cam_id: str | None = None
) -> PreviewSettings:
    """Idle / live publish settings.

    Geometry + mode + soft fps come from ``idle_encode_ask`` (Lite@10) so the
    operator science modal cannot leave a dishonest 16:9 idle encode. Transport
    / MediaMTX knobs still come from ``preview:`` yaml.
    """
    raw = (cfg or {}).get("preview") or {}
    transport = str(raw.get("transport", "mpegts")).strip().lower()
    if transport not in ("webrtc", "mpegts", "udp", "ssh_annex_b", "whep"):
        transport = "mpegts"
    idle = idle_encode_ask(cfg)
    # Prefer baked idle ask; allow legacy per-cam override only if still present.
    sensor_mode = idle.sensor_mode
    if cam_id:
        cams = (cfg or {}).get("cam_sensor_mode") or {}
        if isinstance(cams, dict) and cam_id in cams:
            sensor_mode = normalize_sensor_mode(str(cams.get(cam_id)))
    whep_ingest = str(raw.get("whep_ingest", "cam_mpegts")).strip().lower()
    if whep_ingest not in ("cam_mpegts", "nvr_annexb"):
        whep_ingest = "cam_mpegts"
    try:
        buf = int(raw.get("buffer_count", idle.buffer_count))
    except (TypeError, ValueError):
        buf = idle.buffer_count
    # Honor yaml (Mode 2 litmus uses 2). Do not clamp to Mode-1 soft-30 default of 6.
    buf = max(1, buf)
    try:
        tee_q = int(raw.get("tee_queue_max", 512))
    except (TypeError, ValueError):
        tee_q = 512
    tee_q = max(32, min(4096, tee_q))
    return PreviewSettings(
        width=idle.width,
        height=idle.height,
        fps_idle=idle.soft_fps,
        fps_record=idle.soft_fps,
        bitrate_kbps=idle.bitrate_kbps,
        buffer_count=buf,
        transport=transport,  # type: ignore[arg-type]
        udp_port=int(raw.get("udp_port", 15550)),
        nvr_host=str(raw.get("nvr_host", "") or "").strip(),
        mediamtx_http=str(
            raw.get("mediamtx_http", "http://127.0.0.1:8889") or "http://127.0.0.1:8889"
        ).rstrip("/"),
        sensor_mode=sensor_mode,
        whep_ingest=whep_ingest,  # type: ignore[arg-type]
        tee_queue_max=tee_q,
    )


def mediamtx_whep_url(settings: PreviewSettings, cam_id: str) -> str:
    """WHEP URL for MQTT cam id path (see deploy/bhvr-nvr/mediamtx/mediamtx.yml)."""
    return f"{settings.mediamtx_http}/{cam_id.strip()}/whep"


def cam_ordinal(cam_id: str) -> int | None:
    """Hostname ordinal from ``bhvr-camN`` / ``camN``; None if not parseable."""
    m = re.search(r"(?:^|[-_])cam(\d+)$", cam_id.strip().lower())
    if not m:
        return None
    return int(m.group(1))


def cam_udp_port(cam_id: str, base_port: int = 15550) -> int:
    """Durable ingest map: ``bhvr-camN`` → UDP ``base_port+N`` (cam0=:15550, cam1=:15551).

    Unknown ids fall back to ``base_port`` (legacy single-port behaviour).
    """
    n = cam_ordinal(cam_id)
    if n is None:
        return int(base_port)
    return int(base_port) + int(n)


def nvr_ingress_ip(cfg: dict[str, Any] | None) -> str:
    settings = preview_settings(cfg)
    if settings.nvr_host:
        return settings.nvr_host
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


def udp_ingest_url(port: int) -> str:
    """NVR-side listen (must bind all interfaces — cams send to wlan IP)."""
    return f"udp://0.0.0.0:{port}?overrun_nonfatal=1&fifo_size=50000000&reuse=1"


def udp_listen_url(port: int, *, timeout_us: int = 20_000_000) -> str:
    """NVR listen URL. ``timeout`` keeps ffmpeg open until first packets (or fail)."""
    return (
        f"udp://0.0.0.0:{port}"
        f"?overrun_nonfatal=1&fifo_size=50000000&reuse=1&timeout={timeout_us}"
    )


def nvr_ffmpeg_udp_to_mpegts_pipe(port: int) -> list[str]:
    # Listener-first: UDP timeout keeps ffmpeg open until cam SPS arrives (~2–4s).
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-fflags",
        "nobuffer+genpts+discardcorrupt",
        "-flags",
        "low_delay",
        "-probesize",
        "1000000",
        "-analyzeduration",
        "2000000",
        "-f",
        "mpegts",
        "-i",
        udp_listen_url(port, timeout_us=25_000_000),
        "-c",
        "copy",
        "-f",
        "mpegts",
        "pipe:1",
    ]


def _cam_ffmpeg_resolve_shell() -> str:
    """Prefer ``~/bin/ffmpeg`` — Zero images often lack apt ffmpeg on PATH."""
    return (
        'FFMPEG=$(command -v ffmpeg || true); '
        '[ -x "$HOME/bin/ffmpeg" ] && FFMPEG="$HOME/bin/ffmpeg"; '
        '[ -n "$FFMPEG" ] || { echo "bhvr: ffmpeg missing (need ~/bin/ffmpeg)" >&2; exit 127; }; '
    )


def _cam_ffmpeg_annexb_to_mpegts_pipe_args() -> str:
    """``-c copy`` remux annex-B stdin → MPEG-TS stdout (shared idle + science)."""
    return (
        '"$FFMPEG" -hide_banner -loglevel warning -nostats '
        "-use_wallclock_as_timestamps 1 "
        "-fflags +genpts+nobuffer+flush_packets -flags low_delay -avioflags direct "
        "-f h264 -i pipe:0 -c copy -muxdelay 0 -muxpreload 0 "
        "-flush_packets 1 -f mpegts pipe:1"
    )


def cam_live_ssh_mpegts_remote(settings: PreviewSettings) -> str:
    """Publish MPEG-TS on SSH stdout (TCP). More reliable than UDP on campus WiFi."""
    bitrate = max(100_000, int(settings.bitrate_kbps) * 1000)
    buf = max(1, int(settings.buffer_count))
    mode = rpicam_mode_flag(settings.sensor_mode)
    # Do NOT pkill -f 'ffmpeg.*mpegts' — that matches this shell's cmdline and
    # suicides the SSH session (0-byte idle/science). Kill by comm name only.
    # Caller must run via ``ssh … bash -s`` with this script on stdin (not
    # ``ssh host 'a | b'`` — that path was delivering 0-byte MPEG-TS).
    return (
        "set -e; "
        "pkill -INT rpicam-vid 2>/dev/null || true; "
        "pkill -x ffmpeg 2>/dev/null || true; sleep 0.3; "
        + _cam_ffmpeg_resolve_shell()
        + f"stdbuf -o0 rpicam-vid -n -t 0{mode} "
        f"--width {settings.width} --height {settings.height} "
        f"--framerate {settings.fps_idle} --codec h264 --inline "
        f"--intra {max(1, settings.fps_idle)} --flush "
        f"--bitrate {bitrate} --denoise cdn_off "
        f"--buffer-count {buf} -o - "
        f"| stdbuf -o0 {_cam_ffmpeg_annexb_to_mpegts_pipe_args()}"
    )


def cam_science_ssh_mpegts_remote(
    *,
    width: int,
    height: int,
    soft_fps: int,
    bitrate_bps: int,
    intra: int,
    sensor_mode: str,
    buffer_count: int,
    pts_remote: str,
    workdir: str,
) -> str:
    """Science capture: HW H.264 + ``--save-pts`` → cam MPEG-TS on SSH stdout.

    NVR writes ``*_video.ts`` and tees the same bytes to live (no NVR remux).
    """
    mode = rpicam_mode_flag(sensor_mode)
    buf = max(1, int(buffer_count))
    fps = max(1, int(soft_fps))
    br = max(100_000, int(bitrate_bps))
    # Caller: ``ssh … bash -s`` + script on stdin (see cam_live_ssh_mpegts_remote).
    return (
        "set -e; "
        f"mkdir -p {workdir}; "
        "pkill -INT rpicam-vid 2>/dev/null || true; "
        "pkill -x ffmpeg 2>/dev/null || true; sleep 1; "
        f"rm -f {pts_remote}; "
        + _cam_ffmpeg_resolve_shell()
        + f"stdbuf -o0 rpicam-vid -n -t 0{mode} "
        f"--width {width} --height {height} "
        f"--framerate {fps} --codec h264 --inline --intra {intra} --flush "
        f"--bitrate {br} --denoise cdn_off "
        f"--buffer-count {buf} "
        f"--save-pts {pts_remote} -o - "
        f"| stdbuf -o0 {_cam_ffmpeg_annexb_to_mpegts_pipe_args()}"
    )


def cam_live_udp_remote(settings: PreviewSettings, nvr_ip: str, port: int) -> str:
    """Remote shell: publish MPEG-TS to NVR (script on cam SD or inline fallback)."""
    script = "~/bhvr-cam/scripts/live_udp_mpegts.sh"
    mode = normalize_sensor_mode(settings.sensor_mode)
    args = (
        f"{settings.width} {settings.height} {settings.fps_idle} "
        f"{settings.bitrate_kbps} {settings.buffer_count} {mode}"
    )
    mode_flag = rpicam_mode_flag(mode)
    return (
        f"test -x {script} && exec {script} {nvr_ip} {port} {args} || "
        f"exec bash -c 'pkill -INT rpicam-vid 2>/dev/null; sleep 0.2; "
        f"stdbuf -o0 rpicam-vid -n -t 0{mode_flag} "
        f"--width {settings.width} --height {settings.height} "
        f"--framerate {settings.fps_idle} --codec h264 --inline "
        f"--intra {settings.fps_idle} --flush "
        f"--bitrate {max(100_000, settings.bitrate_kbps * 1000)} --denoise cdn_off "
        f"--buffer-count {settings.buffer_count} -o - | "
        f"ffmpeg -hide_banner -loglevel warning -nostats "
        f"-use_wallclock_as_timestamps 1 "
        f"-fflags +genpts+nobuffer+flush_packets -flags low_delay -avioflags direct "
        f"-f h264 -i pipe:0 -c copy "
        f"-muxdelay 0 -muxpreload 0 -flush_packets 1 "
        f"-f mpegts udp://{nvr_ip}:{port}?pkt_size=1316'"
    )


def cam_free_encode_remote() -> str:
    """Stop leftover idle/LIVE encodes so libcamera can be re-acquired.

    After USB→WiFi (or a killed SSH), ``rpicam-vid`` often keeps the pipeline
    and the next LIVE fails with "Pipeline handler in use by another process"
    → kiosk banner ONLINE · WiFi · no LIVE.
    """
    return (
        "pkill -INT rpicam-vid 2>/dev/null || true; "
        "pkill -x ffmpeg 2>/dev/null || true; "
        "sleep 0.25; "
        "pkill -9 rpicam-vid 2>/dev/null || true; "
        "pkill -9 -x ffmpeg 2>/dev/null || true; "
        "true"
    )


def cam_live_annexb_remote(settings: PreviewSettings) -> str:
    """Remote shell: HW H.264 annex-B on SSH stdout (no cam-side ffmpeg).

    O1a: NVR remuxes to MPEG-TS for MediaMTX. Same encode shape as science record.
    """
    bitrate = max(100_000, int(settings.bitrate_kbps) * 1000)
    buf = max(1, int(settings.buffer_count))
    mode = rpicam_mode_flag(settings.sensor_mode)
    return (
        f"{cam_free_encode_remote()}; "
        f"exec stdbuf -o0 rpicam-vid -n -t 0{mode} "
        f"--width {settings.width} --height {settings.height} "
        f"--framerate {settings.fps_idle} --codec h264 --inline "
        f"--intra {max(1, settings.fps_idle)} --flush "
        f"--bitrate {bitrate} --denoise cdn_off "
        f"--buffer-count {buf} -o -"
    )


def nvr_ffmpeg_annexb_to_mediamtx_udp(port: int) -> list[str]:
    """NVR: annex-B on stdin → MPEG-TS UDP loopback (MediaMTX path source)."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostats",
        "-fflags",
        "+genpts+nobuffer+flush_packets",
        "-flags",
        "low_delay",
        # Pi SSH annex-B can take >0.5s to first SPS under load; short probe
        # yields "Output file does not contain any stream" and black tiles.
        "-probesize",
        "5000000",
        "-analyzeduration",
        "5000000",
        "-f",
        "h264",
        "-i",
        "pipe:0",
        "-c",
        "copy",
        "-muxdelay",
        "0",
        "-muxpreload",
        "0",
        "-flush_packets",
        "1",
        "-f",
        "mpegts",
        f"udp://127.0.0.1:{int(port)}?pkt_size=1316&overrun_nonfatal=1",
    ]


def cam_stop_udp_remote() -> str:
    return (
        f"{cam_free_encode_remote()}; "
        "pkill -f 'ffmpeg.*udp://' 2>/dev/null || true; "
        "true"
    )


def nvr_ffmpeg_annex_b_to_mpegts_pipe() -> list[str]:
    """Annex-B stdin → MPEG-TS stdout (record live tee / legacy HTTP preview).

    Aggressive probesize so a mid-GOP join does not block for seconds on pipe:0.
    """
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-fflags",
        "+genpts+nobuffer+flush_packets+discardcorrupt",
        "-flags",
        "low_delay",
        "-probesize",
        "32768",
        "-analyzeduration",
        "0",
        "-f",
        "h264",
        "-i",
        "pipe:0",
        "-c",
        "copy",
        "-muxdelay",
        "0",
        "-muxpreload",
        "0",
        "-flush_packets",
        "1",
        "-f",
        "mpegts",
        "pipe:1",
    ]


def feed_queue_to_iterator(
    q: "queue.Queue[bytes | None]",
    stop: threading.Event,
):
    """Yield MPEG-TS (or other) chunks from a capture tee queue until stop/None."""
    while not stop.is_set():
        try:
            item = q.get(timeout=0.25)
        except queue.Empty:
            continue
        if item is None:
            break
        yield item


def idle_rpicam_remote(settings: PreviewSettings) -> str:
    bitrate = max(100_000, int(settings.bitrate_kbps) * 1000)
    mode = rpicam_mode_flag(settings.sensor_mode)
    return (
        "pkill -INT rpicam-vid 2>/dev/null || true; sleep 0.2; "
        f"exec stdbuf -o0 rpicam-vid -n -t 0{mode} "
        f"--width {settings.width} --height {settings.height} "
        f"--framerate {settings.fps_idle} --codec h264 --inline "
        f"--intra {max(1, settings.fps_idle)} --flush "
        f"--bitrate {bitrate} --denoise cdn_off "
        f"--buffer-count {settings.buffer_count} -o -"
    )
