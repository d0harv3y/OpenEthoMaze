"""Kiosk settings helpers (USB push eligibility + soft set list)."""

from __future__ import annotations

from pathlib import Path

from app.kiosk_settings import (
    SOFT_INSTALL,
    cam_tree,
    eligible_usb_cams,
    openethomaze_root,
    soft_bundle_files,
)


def test_openethomaze_root_override() -> None:
    assert openethomaze_root({"cam_bundle_git_root": "/opt/OEM"}) == Path("/opt/OEM")
    assert cam_tree({"cam_bundle_git_root": "/opt/OEM"}) == Path(
        "/opt/OEM/deploy/bhvr-cam"
    )


def test_openethomaze_root_home_deploy_fallback(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    (home / "deploy" / "bhvr-cam").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    assert openethomaze_root({}) == home
    assert cam_tree({}) == home / "deploy" / "bhvr-cam"


def test_eligible_usb_cams_filters() -> None:
    cams = [
        {
            "id": "bhvr-cam0",
            "online": True,
            "link": "usb",
            "ips": {"usb": "192.168.7.10", "wifi": "10.1.2.3"},
            "ip": "192.168.7.10",
        },
        {
            "id": "bhvr-cam1",
            "online": True,
            "link": "wifi",
            "ips": {"usb": "192.168.7.11", "wifi": "10.1.2.4"},
            "ip": "10.1.2.4",
        },
        {
            "id": "bhvr-cam2",
            "online": False,
            "link": "usb",
            "ips": {"usb": "192.168.7.12"},
            "ip": "192.168.7.12",
        },
        {
            "id": "bhvr-cam3",
            "online": True,
            "link": "usb",
            "ips": {"usb": "192.168.7.13"},
            "ip": "192.168.7.13",
        },
    ]
    rows = eligible_usb_cams(cams, ssh_ok=lambda ip: ip.endswith(".10"))
    by_id = {r["id"]: r for r in rows}
    assert "bhvr-cam0" in by_id and by_id["bhvr-cam0"]["eligible"] is True
    assert "bhvr-cam1" not in by_id  # wifi link
    assert "bhvr-cam2" not in by_id  # offline
    assert "bhvr-cam3" in by_id and by_id["bhvr-cam3"]["eligible"] is False


def test_soft_bundle_files_repo_tree() -> None:
    # Prefer workspace tree when running from OpenEthoMaze checkout.
    here = Path(__file__).resolve()
    # .../deploy/bhvr-kiosk/tests/this → parents[3] = OpenEthoMaze
    oem = here.parents[3]
    tree = oem / "deploy" / "bhvr-cam"
    if not tree.is_dir():
        return
    rows = soft_bundle_files(tree)
    assert len(rows) == len(SOFT_INSTALL)
    missing = [r["rel"] for r in rows if not r["present"]]
    assert missing == [], f"soft set gaps: {missing}"
