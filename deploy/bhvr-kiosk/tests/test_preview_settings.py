from app.preview import (
    cam_live_annexb_remote,
    cam_live_ssh_mpegts_remote,
    cam_live_udp_remote,
    cam_ordinal,
    cam_science_ssh_mpegts_remote,
    cam_sensor_mode,
    cam_udp_port,
    mediamtx_whep_url,
    normalize_sensor_mode,
    nvr_ffmpeg_annexb_to_mediamtx_udp,
    nvr_ingress_ip,
    preview_settings,
    rpicam_mode_flag,
)


def test_preview_defaults_mpegts() -> None:
    s = preview_settings({})
    assert s.transport == "mpegts"
    assert s.udp_port == 15550
    # Idle ask: Lite@10 (grill Q16 B), regardless of legacy yaml width.
    assert s.width == 640 and s.height == 480
    assert s.fps_idle == 10
    assert s.sensor_mode == "640:480"
    assert s.buffer_count == 6  # default when unset


def test_preview_buffer_count_honors_yaml() -> None:
    s = preview_settings({"preview": {"transport": "mpegts", "buffer_count": 2}})
    assert s.buffer_count == 2


def test_preview_tee_queue_max_default_and_clamp() -> None:
    assert preview_settings({}).tee_queue_max == 512
    assert preview_settings({"preview": {"tee_queue_max": 64}}).tee_queue_max == 64
    assert preview_settings({"preview": {"tee_queue_max": 8}}).tee_queue_max == 32
    assert preview_settings({"preview": {"tee_queue_max": 99999}}).tee_queue_max == 4096


def test_preview_whep_settings() -> None:
    s = preview_settings(
        {
            "preview": {
                "transport": "whep",
                "udp_port": 15550,
                "mediamtx_http": "http://127.0.0.1:8889/",
            }
        }
    )
    assert s.transport == "whep"
    assert s.mediamtx_http == "http://127.0.0.1:8889"
    assert mediamtx_whep_url(s, "bhvr-cam1") == "http://127.0.0.1:8889/bhvr-cam1/whep"


def test_cam_udp_remote_targets_nvr() -> None:
    s = preview_settings({"preview": {"transport": "mpegts", "udp_port": 15550}})
    remote = cam_live_udp_remote(s, "10.248.238.22", 15550)
    assert "udp://10.248.238.22:15550" in remote
    assert "rpicam-vid" in remote


def test_nvr_ingress_override() -> None:
    ip = nvr_ingress_ip({"preview": {"nvr_host": "10.0.0.99"}})
    assert ip == "10.0.0.99"


def test_sensor_mode_normalize_and_flag() -> None:
    assert normalize_sensor_mode("1296x972") == "1296:972"
    assert rpicam_mode_flag("auto") == ""
    assert rpicam_mode_flag("1296:972") == " --mode 1296:972:10:P"


def test_cam_sensor_mode_per_cam_override() -> None:
    """Legacy cam_sensor_mode override still applied if present (debug escape)."""
    cfg = {
        "preview": {"buffer_count": 6},
        "cam_sensor_mode": {"bhvr-cam1": "1296:972"},
    }
    assert cam_sensor_mode(cfg, "bhvr-cam1") == "1296:972"
    s = preview_settings(cfg, cam_id="bhvr-cam1")
    assert s.sensor_mode == "1296:972"
    # Geometry stays idle Lite even when mode overridden.
    assert s.width == 640 and s.fps_idle == 10
    remote = cam_live_udp_remote(s, "192.168.7.1", 15550)
    assert "1296:972" in remote


def test_cam_udp_port_ordinal_map() -> None:
    assert cam_ordinal("bhvr-cam0") == 0
    assert cam_ordinal("bhvr-cam1") == 1
    assert cam_ordinal("bhvr-cam3") == 3
    assert cam_ordinal("weird") is None
    assert cam_udp_port("bhvr-cam0") == 15550
    assert cam_udp_port("bhvr-cam1") == 15551
    assert cam_udp_port("bhvr-cam3", 15550) == 15553
    assert cam_udp_port("unknown-host") == 15550


def test_whep_ingest_nvr_annexb() -> None:
    s = preview_settings({"preview": {"transport": "whep", "whep_ingest": "nvr_annexb"}})
    assert s.whep_ingest == "nvr_annexb"
    remote = cam_live_annexb_remote(s)
    assert "rpicam-vid" in remote
    assert "ffmpeg" not in remote
    assert "-o -" in remote
    argv = nvr_ffmpeg_annexb_to_mediamtx_udp(15551)
    assert "ffmpeg" in argv[0]
    assert "udp://127.0.0.1:15551" in argv[-1]


def test_cam_live_ssh_mpegts_uses_cam_ffmpeg() -> None:
    s = preview_settings({"preview": {"transport": "mpegts", "buffer_count": 3}})
    remote = cam_live_ssh_mpegts_remote(s)
    assert remote.startswith("set -e")
    assert "rpicam-vid" in remote
    assert "HOME/bin/ffmpeg" in remote
    assert "-f mpegts pipe:1" in remote
    assert "--save-pts" not in remote
    assert "pkill -x ffmpeg" in remote


def test_cam_science_ssh_mpegts_keeps_save_pts() -> None:
    remote = cam_science_ssh_mpegts_remote(
        width=1296,
        height=972,
        soft_fps=20,
        bitrate_bps=2_500_000,
        intra=20,
        sensor_mode="1296:972",
        buffer_count=6,
        pts_remote="/home/admin/bhvr-current/timestamps.pts",
        workdir="/home/admin/bhvr-current",
    )
    assert remote.startswith("set -e")
    assert "--save-pts /home/admin/bhvr-current/timestamps.pts" in remote
    assert "--width 1296" in remote and "--height 972" in remote
    assert "--framerate 20" in remote
    assert "HOME/bin/ffmpeg" in remote
    assert "-f mpegts pipe:1" in remote
    assert "-c copy" in remote
