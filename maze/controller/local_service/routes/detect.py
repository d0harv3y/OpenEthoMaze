"""POST /orm/detect — YOLO object detection (Phase B6)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..detect import DetectError, run_detect_image, run_detect_video_frame
from ..yolo import (
    YoloDependencyError,
    YoloError,
    YoloInferenceError,
    YoloLoadError,
    YoloNotConfiguredError,
    is_yolo_configured,
)

if TYPE_CHECKING:
    from flask import Blueprint


def register_detect_routes(bp: Blueprint) -> None:
    from flask import current_app, jsonify, request

    @bp.post("/detect")
    def orm_detect():
        if not is_yolo_configured():
            return (
                jsonify(
                    {
                        "error": (
                            "YOLO not configured (set MAZE_YOLO_WEIGHTS; "
                            "install with: uv sync --extra local-service)"
                        )
                    }
                ),
                503,
            )

        config = current_app.config["LOCAL_SERVICE_CONFIG"]
        weights_param = request.args.get("weights")

        try:
            if request.files and "image" in request.files:
                image_file = request.files["image"]
                payload = image_file.read()
                result = run_detect_image(
                    config, payload, weights_param=weights_param
                )
                return jsonify(result.to_json_dict())

            body = request.get_json(silent=True)
            if isinstance(body, dict) and "video_path" in body:
                video_path = body.get("video_path")
                if not isinstance(video_path, str) or not video_path.strip():
                    return jsonify({"error": "video_path must be a non-empty string"}), 400
                frame_raw = body.get("frame_index", 0)
                try:
                    frame_index = int(frame_raw)
                except (TypeError, ValueError):
                    return jsonify({"error": "frame_index must be an integer"}), 400
                result = run_detect_video_frame(
                    config,
                    video_path.strip(),
                    frame_index,
                    weights_param=weights_param,
                )
                return jsonify(result.to_json_dict())

            return (
                jsonify(
                    {
                        "error": (
                            "provide multipart field 'image' or JSON "
                            '{"video_path": "...", "frame_index": 0}'
                        )
                    }
                ),
                400,
            )
        except DetectError as exc:
            return jsonify({"error": str(exc)}), 400
        except YoloNotConfiguredError as exc:
            return jsonify({"error": str(exc)}), 503
        except YoloDependencyError as exc:
            return jsonify({"error": str(exc)}), 503
        except YoloLoadError as exc:
            return jsonify({"error": str(exc)}), 503
        except YoloInferenceError as exc:
            return jsonify({"error": str(exc)}), 502
        except YoloError as exc:
            return jsonify({"error": str(exc)}), 503
