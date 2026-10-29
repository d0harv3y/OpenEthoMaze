from app.encode_ask import (
    DEFAULT_BUFFER_COUNT,
    encode_ask,
    idle_encode_ask,
    normalize_science_size,
    normalize_soft_fps,
    science_encode_ask,
)


def test_standard_and_lite_geom() -> None:
    s = encode_ask("standard", 20)
    assert s.width == 1296 and s.height == 972
    assert s.sensor_mode == "1296:972"
    assert s.soft_fps == 20
    assert s.buffer_count == DEFAULT_BUFFER_COUNT
    lit = encode_ask("lite", 10)
    assert lit.width == 640 and lit.height == 480
    assert lit.sensor_mode == "640:480"


def test_legacy_profile_aliases() -> None:
    assert normalize_science_size("480p") == "lite"
    assert normalize_science_size("720p") == "standard"
    assert normalize_science_size("1080p") == "standard"
    ask = science_encode_ask("720p30", 30)
    assert ask.size_id == "standard"
    assert ask.soft_fps == 30


def test_soft_fps_allowlist() -> None:
    assert normalize_soft_fps(20) == 20
    assert normalize_soft_fps(19) == 20  # nearest
    assert normalize_soft_fps(12) == 10


def test_idle_is_lite_10() -> None:
    idle = idle_encode_ask({"preview": {"buffer_count": 6}, "record": {"bitrate_kbps": 9999}})
    assert idle.size_id == "lite"
    assert idle.soft_fps == 10
    assert idle.width == 640
    assert idle.bitrate_kbps < 2000  # not forced to record override
