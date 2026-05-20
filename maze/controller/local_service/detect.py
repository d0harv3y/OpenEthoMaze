"""Detection orchestration for /orm/detect (Phase B6)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np

from .sandbox import PathNotAllowedError
from .yolo import (
    Detection,
    YoloNotConfiguredError,
    is_yolo_configured,
    predict,
    resolve_weights_path,
)

if TYPE_CHECKING:
    from .config import LocalServiceConfig


class DetectError(ValueError):
    """Invalid detect request."""


@dataclass(frozen=True)
class DetectResult:
    source: str
    weights: str
    detections: tuple[Detection, ...]
    video_path: str | None = None
    frame_index: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source": self.source,
            "weights": self.weights,
            "detections": [d.to_json_dict() for d in self.detections],
        }
        if self.video_path is not None:
            payload["video_path"] = self.video_path
        if self.frame_index is not None:
            payload["frame_index"] = self.frame_index
        return payload


def run_detect_image(
    config: LocalServiceConfig,
    image_bytes: bytes,
    *,
    weights_param: str | None = None,
) -> DetectResult:
    if not is_yolo_configured():
        raise YoloNotConfiguredError(
            "YOLO not configured (set MAZE_YOLO_WEIGHTS to a .pt file)"
        )
    image_bgr = _decode_image_bytes(image_bytes)
    weights = resolve_weights_path(weights_param)
    detections = tuple(predict(image_bgr, weights))
    return DetectResult(
        source="image",
        weights=str(weights),
        detections=detections,
    )


def run_detect_video_frame(
    config: LocalServiceConfig,
    video_path: str,
    frame_index: int,
    *,
    weights_param: str | None = None,
) -> DetectResult:
    if not is_yolo_configured():
        raise YoloNotConfiguredError(
            "YOLO not configured (set MAZE_YOLO_WEIGHTS to a .pt file)"
        )
    if frame_index < 0:
        raise DetectError("frame_index must be >= 0")

    sandbox = config.sandbox()
    try:
        resolved_video = sandbox.resolve(video_path, must_exist=True)
    except PathNotAllowedError as exc:
        raise DetectError(f"video_path not allowed: {exc}") from exc

    image_bgr = _read_video_frame(resolved_video, frame_index)
    weights = resolve_weights_path(weights_param)
    detections = tuple(predict(image_bgr, weights))
    display_path = _display_path(resolved_video, config.data_root)
    return DetectResult(
        source="video_frame",
        weights=str(weights),
        detections=detections,
        video_path=display_path,
        frame_index=frame_index,
    )


def _decode_image_bytes(data: bytes) -> np.ndarray:
    import cv2

    if not data:
        raise DetectError("image payload is empty")
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise DetectError("could not decode image bytes")
    return image


def _read_video_frame(video_path: Path, frame_index: int) -> np.ndarray:
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise DetectError(f"could not open video: {video_path}")
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok or frame is None:
        raise DetectError(f"could not read frame {frame_index} from {video_path}")
    return frame


def _display_path(path: Path, data_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(data_root.resolve()))
    except ValueError:
        return str(path)
