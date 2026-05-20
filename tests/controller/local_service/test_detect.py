"""POST /orm/detect and YOLO detect orchestration (Phase B PR-B6).

Requires: core + dev (see ``fixtures.py``). YOLO inference mocked in CI (no ``.pt``).
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pytest

pytest_plugins = ["tests.controller.local_service.fixtures"]

from maze.controller.local_service.config import build_config
from maze.controller.local_service.detect import DetectError, run_detect_image, run_detect_video_frame
from maze.controller.local_service.yolo import (
    Detection,
    YoloLoadError,
    reset_yolo_state,
    resolve_weights_path,
)


@pytest.fixture(autouse=True)
def _reset_yolo() -> None:
    reset_yolo_state()
    yield
    reset_yolo_state()


@pytest.fixture
def yolo_weights(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    weights = tmp_path / "default.pt"
    weights.write_bytes(b"fake-weights")
    monkeypatch.setenv("MAZE_YOLO_WEIGHTS", str(weights))
    monkeypatch.delenv("MAZE_YOLO_WEIGHTS_DIR", raising=False)
    return weights


@pytest.fixture
def fake_detection() -> list[Detection]:
    return [
        Detection(
            class_id=0,
            class_name="mouse",
            score=0.9,
            box=(10.0, 20.0, 30.0, 40.0),
        )
    ]


def test_post_detect_returns_503_when_yolo_not_configured(local_app, tiny_png: bytes) -> None:
    client = local_app.test_client()
    response = client.post(
        "/orm/detect",
        data={"image": (io.BytesIO(tiny_png), "frame.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 503
    assert "MAZE_YOLO_WEIGHTS" in response.get_json()["error"]


def test_run_detect_image_with_mocked_yolo(
    minimal_h5web_static: tuple[Path, Path],
    yolo_weights: Path,
    tiny_png: bytes,
    fake_detection: list[Detection],
    mock_decode_image_bgr: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h5_base, _ = minimal_h5web_static
    config = build_config(h5_base)

    import maze.controller.local_service.detect as detect_mod

    monkeypatch.setattr(detect_mod, "predict", lambda _img, _w: fake_detection)

    result = run_detect_image(config, tiny_png)
    assert result.source == "image"
    assert result.detections[0].class_name == "mouse"
    assert result.weights == str(yolo_weights.resolve())


def test_post_detect_multipart_image(
    local_app,
    yolo_weights: Path,
    tiny_png: bytes,
    fake_detection: list[Detection],
    mock_decode_image_bgr: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import maze.controller.local_service.detect as detect_mod

    monkeypatch.setattr(detect_mod, "predict", lambda _img, _w: fake_detection)

    client = local_app.test_client()
    response = client.post(
        "/orm/detect",
        data={"image": (io.BytesIO(tiny_png), "frame.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["source"] == "image"
    assert len(payload["detections"]) == 1
    assert payload["detections"][0]["class_name"] == "mouse"


def test_run_detect_video_rejects_path_outside_root(
    minimal_h5web_static: tuple[Path, Path],
    yolo_weights: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h5_base, _ = minimal_h5web_static
    outside = h5_base.parent / "outside.mp4"
    outside.write_bytes(b"\x00")
    config = build_config(h5_base)

    import maze.controller.local_service.detect as detect_mod

    monkeypatch.setattr(detect_mod, "predict", lambda _img, _w: [])

    with pytest.raises(DetectError, match="not allowed"):
        run_detect_video_frame(config, str(outside), 0)


def test_run_detect_video_frame_with_mocked_io(
    minimal_h5web_static: tuple[Path, Path],
    yolo_weights: Path,
    fake_detection: list[Detection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h5_base, _ = minimal_h5web_static
    video = h5_base / "trial.mp4"
    video.write_bytes(b"placeholder")
    config = build_config(h5_base)

    import maze.controller.local_service.detect as detect_mod

    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    monkeypatch.setattr(detect_mod, "_read_video_frame", lambda _path, _idx: frame)
    monkeypatch.setattr(detect_mod, "predict", lambda _img, _w: fake_detection)

    result = run_detect_video_frame(config, "trial.mp4", 3)
    assert result.source == "video_frame"
    assert result.frame_index == 3
    assert result.video_path == "trial.mp4"
    assert result.detections[0].class_name == "mouse"


def test_resolve_weights_rejects_path_outside_weights_dir(
    yolo_weights: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allowed_dir = tmp_path / "models"
    allowed_dir.mkdir()
    inside = allowed_dir / "arena.pt"
    inside.write_bytes(b"x")
    outside = tmp_path / "other.pt"
    outside.write_bytes(b"y")
    monkeypatch.setenv("MAZE_YOLO_WEIGHTS_DIR", str(allowed_dir))

    assert resolve_weights_path("arena.pt") == inside.resolve()
    with pytest.raises(YoloLoadError, match="MAZE_YOLO_WEIGHTS_DIR"):
        resolve_weights_path(str(outside))


def test_post_detect_json_video_path(local_app, yolo_weights: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import maze.controller.local_service.detect as detect_mod

    frame = np.zeros((4, 4, 3), dtype=np.uint8)

    monkeypatch.setattr(detect_mod, "_read_video_frame", lambda _path, _idx: frame)
    monkeypatch.setattr(
        detect_mod,
        "predict",
        lambda _img, _w: [
            Detection(class_id=1, class_name="object", score=0.5, box=(0.0, 0.0, 1.0, 1.0))
        ],
    )

    client = local_app.test_client()
    response = client.post(
        "/orm/detect",
        json={"video_path": "missing.mp4", "frame_index": 0},
    )
    assert response.status_code == 400


@pytest.mark.yolo_integration
def test_detect_with_real_weights(minimal_h5web_static: tuple[Path, Path], tiny_png: bytes) -> None:
    weights_env = os.environ.get("MAZE_YOLO_WEIGHTS", "").strip()
    if not weights_env:
        pytest.skip("MAZE_YOLO_WEIGHTS not set (optional YOLO integration test)")
    if not Path(weights_env).is_file():
        pytest.skip(f"MAZE_YOLO_WEIGHTS file not found: {weights_env}")

    try:
        import ultralytics  # noqa: F401
    except ImportError:
        pytest.fail(
            "MAZE_YOLO_WEIGHTS is set but ultralytics is not installed; "
            "run: uv sync --extra local-service"
        )

    h5_base, _ = minimal_h5web_static
    config = build_config(h5_base)
    result = run_detect_image(config, tiny_png)
    assert result.source == "image"
