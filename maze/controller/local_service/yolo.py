"""Optional ultralytics YOLO backend for /orm/detect (Phase B6).

Requires ``uv sync --extra local-service``. No detect fallback when weights are
unset — routes return 503 (see ``detect.py`` / ``routes/detect.py``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

_YOLO_MODEL: object | None = None
_YOLO_LOADED_WEIGHTS: Path | None = None


class YoloError(Exception):
    """Base error for YOLO loading or inference."""


class YoloNotConfiguredError(YoloError):
    """No default weights configured (``MAZE_YOLO_WEIGHTS``)."""


class YoloDependencyError(YoloError):
    """ultralytics missing (``local-service`` extra)."""


class YoloLoadError(YoloError):
    """Weights path invalid or model failed to load."""


class YoloInferenceError(YoloError):
    """Inference failed."""


@dataclass(frozen=True)
class Detection:
    class_id: int
    class_name: str
    score: float
    box: tuple[float, float, float, float]

    def to_json_dict(self) -> dict[str, Any]:
        x1, y1, x2, y2 = self.box
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "score": self.score,
            "box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        }


def configured_default_weights() -> Path | None:
    raw = os.environ.get("MAZE_YOLO_WEIGHTS", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if path.is_file() else None


def configured_weights_dir() -> Path | None:
    raw = os.environ.get("MAZE_YOLO_WEIGHTS_DIR", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if path.is_dir() else None


def is_yolo_configured() -> bool:
    return configured_default_weights() is not None


def is_yolo_loaded() -> bool:
    return _YOLO_MODEL is not None


def reset_yolo_state() -> None:
    """Clear cached model (tests only)."""
    global _YOLO_MODEL, _YOLO_LOADED_WEIGHTS
    _YOLO_MODEL = None
    _YOLO_LOADED_WEIGHTS = None


def resolve_weights_path(weights_param: str | None) -> Path:
    """Resolve default or alternate ``.pt`` weights under policy."""
    default = configured_default_weights()
    if default is None:
        raise YoloNotConfiguredError(
            "YOLO not configured (set MAZE_YOLO_WEIGHTS to a .pt file)"
        )
    if weights_param is None or not str(weights_param).strip():
        return default

    candidate = Path(weights_param).expanduser()
    if not candidate.is_absolute():
        weights_dir = configured_weights_dir()
        if weights_dir is None:
            raise YoloLoadError(
                "alternate weights require MAZE_YOLO_WEIGHTS_DIR when using a relative path"
            )
        candidate = (weights_dir / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not candidate.is_file() or candidate.suffix.lower() != ".pt":
        raise YoloLoadError(f"weights must be an existing .pt file: {candidate}")

    weights_dir = configured_weights_dir()
    if weights_dir is not None:
        try:
            candidate.relative_to(weights_dir.resolve())
        except ValueError as exc:
            raise YoloLoadError(
                f"weights must be under MAZE_YOLO_WEIGHTS_DIR ({weights_dir})"
            ) from exc
    elif candidate != default.resolve():
        raise YoloLoadError(
            "alternate weights require MAZE_YOLO_WEIGHTS_DIR or omit the weights parameter"
        )
    return candidate


def load_yolo(weights_path: Path) -> object:
    global _YOLO_MODEL, _YOLO_LOADED_WEIGHTS
    resolved = weights_path.resolve()
    if _YOLO_MODEL is not None and _YOLO_LOADED_WEIGHTS == resolved:
        return _YOLO_MODEL

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise YoloDependencyError(
            "ultralytics is not installed; run: uv sync --extra local-service"
        ) from exc

    try:
        _YOLO_MODEL = YOLO(str(resolved))
    except Exception as exc:
        raise YoloLoadError(f"failed to load YOLO weights at {resolved}: {exc}") from exc
    _YOLO_LOADED_WEIGHTS = resolved
    return _YOLO_MODEL


def predict(image_bgr: np.ndarray, weights_path: Path) -> list[Detection]:
    """Run YOLO on a BGR ``numpy`` image."""
    if image_bgr.size == 0:
        raise YoloInferenceError("empty image")
    model = load_yolo(weights_path)
    try:
        results = model.predict(source=image_bgr, verbose=False)
    except Exception as exc:
        raise YoloInferenceError(f"YOLO predict failed: {exc}") from exc
    return _parse_results(results)


def _parse_results(results: object) -> list[Detection]:
    if not results:
        return []
    first = results[0]
    names = getattr(first, "names", {}) or {}
    boxes = getattr(first, "boxes", None)
    if boxes is None:
        return []

    detections: list[Detection] = []
    for box in boxes:
        cls_tensor = getattr(box, "cls", None)
        if cls_tensor is None:
            continue
        class_id = int(cls_tensor[0].item() if hasattr(cls_tensor[0], "item") else cls_tensor[0])
        conf = float(box.conf[0].item() if hasattr(box.conf[0], "item") else box.conf[0])
        xyxy = box.xyxy[0]
        coords = (
            float(xyxy[0].item() if hasattr(xyxy[0], "item") else xyxy[0]),
            float(xyxy[1].item() if hasattr(xyxy[1], "item") else xyxy[1]),
            float(xyxy[2].item() if hasattr(xyxy[2], "item") else xyxy[2]),
            float(xyxy[3].item() if hasattr(xyxy[3], "item") else xyxy[3]),
        )
        class_name = str(names.get(class_id, str(class_id)))
        detections.append(
            Detection(class_id=class_id, class_name=class_name, score=conf, box=coords)
        )
    return detections
