"""WebRTC focus preview: NVR reads cam UDP MPEG-TS via aiortc MediaPlayer."""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from typing import Any

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer

from app.preview import PreviewSettings, udp_ingest_url

logger = logging.getLogger(__name__)

_pcs: dict[str, RTCPeerConnection] = {}
_players: dict[str, MediaPlayer] = {}
_lock = asyncio.Lock()


async def close_webrtc_preview(cam_id: str) -> None:
    async with _lock:
        pc = _pcs.pop(cam_id, None)
        player = _players.pop(cam_id, None)
    if player is not None:
        try:
            player.stop()
        except Exception:
            logger.exception("MediaPlayer.stop failed for %s", cam_id)
    if pc is not None:
        await pc.close()


async def close_all_webrtc_previews() -> None:
    async with _lock:
        ids = list(_pcs.keys())
    for cam_id in ids:
        await close_webrtc_preview(cam_id)


def wait_for_udp_packets(port: int, timeout_s: float = 8.0, need: int = 5) -> int:
    """Block until a few UDP datagrams arrive (or timeout). SO_REUSEPORT so ffmpeg can bind next."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        pass
    sock.bind(("0.0.0.0", port))
    sock.settimeout(0.5)
    got = 0
    deadline = time.time() + timeout_s
    while time.time() < deadline and got < need:
        try:
            sock.recvfrom(65535)
            got += 1
        except socket.timeout:
            continue
    sock.close()
    return got


def _open_media_player(port: int) -> MediaPlayer:
    url = udp_ingest_url(port)
    player = MediaPlayer(
        url,
        format="mpegts",
        options={
            "fflags": "nobuffer+discardcorrupt",
            "flags": "low_delay",
            "probesize": "1000000",
            "analyzeduration": "500000",
        },
    )
    if player.video is None:
        player.stop()
        raise RuntimeError("MediaPlayer did not expose a video track (no UDP yet?)")
    return player


async def handle_webrtc_offer(
    cam_id: str,
    offer_sdp: str,
    offer_type: str,
    settings: PreviewSettings,
    port: int,
) -> RTCSessionDescription:
    _ = settings
    await close_webrtc_preview(cam_id)

    # MediaPlayer() is sync and can block the event loop for a long time on UDP.
    player = await asyncio.wait_for(
        asyncio.to_thread(_open_media_player, port),
        timeout=20.0,
    )

    pc = RTCPeerConnection()
    pc.addTrack(player.video)
    if player.audio:
        pc.addTrack(player.audio)

    offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    async with _lock:
        _pcs[cam_id] = pc
        _players[cam_id] = player

    @pc.on("connectionstatechange")
    async def _on_state_change() -> None:
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await close_webrtc_preview(cam_id)

    assert pc.localDescription is not None
    return pc.localDescription


def webrtc_status() -> dict[str, Any]:
    return {"sessions": sorted(_pcs.keys())}
