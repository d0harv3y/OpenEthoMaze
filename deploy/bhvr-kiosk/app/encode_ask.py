"""Science / idle encode ask — 4:3 OV5647 bins (grill 11 / task 13).

Cam-side knobs only. Display decimation stays on the kiosk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ScienceSizeId = Literal["standard", "lite"]
SCIENCE_SIZE_IDS: tuple[str, ...] = ("standard", "lite")
SCIENCE_FPS_OPTIONS: tuple[int, ...] = (30, 20, 15, 10)
DEFAULT_SCIENCE_SIZE: ScienceSizeId = "lite"
DEFAULT_SCIENCE_FPS = 30
# Fallback only when operator state is unavailable (preview_settings base).
# Live WHEP/mpegts idle uses live_preview_settings → Session soft_fps (default 30).
IDLE_SIZE: ScienceSizeId = "lite"
IDLE_FPS = DEFAULT_SCIENCE_FPS
DEFAULT_BUFFER_COUNT = 6

# Operator label → native 4:3 mode + output (no crop / stretch).
_SIZE_GEOM: dict[str, tuple[int, int, str]] = {
    "standard": (1296, 972, "1296:972"),
    "lite": (640, 480, "640:480"),
}

# Legacy session profile tokens → size id.
_PROFILE_ALIASES: dict[str, str] = {
    "standard": "standard",
    "lite": "lite",
    "480p": "lite",
    "480p30": "lite",
    "720p": "standard",
    "720p20": "standard",
    "720p30": "standard",
    # Was 16:9 crop; map to Standard (2×2) — FOV-honest replacement.
    "1080p": "standard",
}


@dataclass(frozen=True)
class EncodeAsk:
    """Everything that must be on the cam ``rpicam-vid`` line."""

    size_id: str
    width: int
    height: int
    sensor_mode: str
    soft_fps: int
    bitrate_kbps: int
    buffer_count: int = DEFAULT_BUFFER_COUNT

    @property
    def label(self) -> str:
        nice = "Standard" if self.size_id == "standard" else "Lite"
        return f"{nice} {self.width}×{self.height} @{self.soft_fps}"

    @property
    def bitrate_bps(self) -> int:
        return max(100_000, int(self.bitrate_kbps) * 1000)

    @property
    def intra(self) -> int:
        return max(1, int(self.soft_fps))


def normalize_science_size(raw: str | None) -> str:
    key = str(raw or DEFAULT_SCIENCE_SIZE).strip().lower()
    return _PROFILE_ALIASES.get(key, DEFAULT_SCIENCE_SIZE)


def normalize_soft_fps(raw: int | str | None, *, default: int = DEFAULT_SCIENCE_FPS) -> int:
    try:
        fps = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        fps = default
    if fps not in SCIENCE_FPS_OPTIONS:
        # Nearest allowlisted value.
        fps = min(SCIENCE_FPS_OPTIONS, key=lambda x: abs(x - fps))
    return fps


def bitrate_for(size_id: str, soft_fps: int) -> int:
    """Derive kbps from size×fps (Settings override deferred)."""
    if size_id == "lite":
        return 800 if soft_fps <= 15 else 1200
    return 1800 if soft_fps <= 15 else 2500


def encode_ask(
    size_id: str,
    soft_fps: int,
    *,
    cfg: dict[str, Any] | None = None,
    buffer_count: int | None = None,
) -> EncodeAsk:
    _ = cfg  # reserved for Settings bitrate override later
    size = normalize_science_size(size_id)
    fps = normalize_soft_fps(soft_fps)
    width, height, mode = _SIZE_GEOM[size]
    buf = DEFAULT_BUFFER_COUNT if buffer_count is None else max(1, int(buffer_count))
    return EncodeAsk(
        size_id=size,
        width=width,
        height=height,
        sensor_mode=mode,
        soft_fps=fps,
        bitrate_kbps=bitrate_for(size, fps),
        buffer_count=buf,
    )


def idle_encode_ask(cfg: dict[str, Any] | None = None) -> EncodeAsk:
    """No session: always Lite@10 (grill Q16 B)."""
    raw = (cfg or {}).get("preview") or {}
    buf = raw.get("buffer_count")
    try:
        buf_i = int(buf) if buf is not None else DEFAULT_BUFFER_COUNT
    except (TypeError, ValueError):
        buf_i = DEFAULT_BUFFER_COUNT
    # Mode 1 default remains 6 when unset; Mode 2 may set preview.buffer_count: 2.
    return encode_ask(IDLE_SIZE, IDLE_FPS, cfg=cfg, buffer_count=max(1, buf_i))


def science_encode_ask(
    profile: str,
    soft_fps: int | None,
    cfg: dict[str, Any] | None = None,
) -> EncodeAsk:
    """Session science ask from profile (size) + soft_fps."""
    raw = (cfg or {}).get("record") or {}
    fps = soft_fps if soft_fps is not None else raw.get("soft_fps", DEFAULT_SCIENCE_FPS)
    return encode_ask(profile, int(fps) if fps is not None else DEFAULT_SCIENCE_FPS, cfg=cfg)


def science_size_options() -> list[dict[str, Any]]:
    return [
        {
            "id": "standard",
            "label": "Standard",
            "width": 1296,
            "height": 972,
            "mode": "1296:972",
        },
        {
            "id": "lite",
            "label": "Lite",
            "width": 640,
            "height": 480,
            "mode": "640:480",
        },
    ]
