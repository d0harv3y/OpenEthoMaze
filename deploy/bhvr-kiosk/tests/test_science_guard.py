"""Science promote guard: late idle-stop must not pkill a claimed capture cam."""

from __future__ import annotations

import app.main as main


def setup_function() -> None:
    main._science_guard_release()
    with main._capture_lock:
        main._captures.clear()


def teardown_function() -> None:
    setup_function()


def test_science_guard_blocks_free_when_claimed() -> None:
    main._science_guard_claim(["bhvr-cam0"])
    assert main._science_guarded("bhvr-cam0")
    assert not main._science_guarded("bhvr-cam1")
    # free is a no-op when guarded (no SSH attempted — empty hosts list)
    main._free_cam_encode_hosts({"ssh_user": "admin"}, "bhvr-cam0", hosts=[])
    main._science_guard_release(["bhvr-cam0"])
    assert not main._science_guarded("bhvr-cam0")


def test_science_guard_blocks_free_when_capturing() -> None:
    with main._capture_lock:
        main._captures["bhvr-cam0"] = {"proc": None}
    assert main._science_guarded("bhvr-cam0")
    main._free_cam_encode_hosts({"ssh_user": "admin"}, "bhvr-cam0", hosts=[])
