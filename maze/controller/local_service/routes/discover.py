"""POST /orm/discover — file discovery under sandboxed roots (Phase B5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..discover import DiscoverError, DiscoverParseError, run_discover
from ..glob_safe import GlobLimitError, GlobTimeoutError
from ..llm import LlmDependencyError, LlmError, LlmInferenceError, LlmLoadError

if TYPE_CHECKING:
    from flask import Blueprint


def register_discover_routes(bp: Blueprint) -> None:
    from flask import current_app, jsonify, request

    @bp.post("/discover")
    def orm_discover():
        config = current_app.config["LOCAL_SERVICE_CONFIG"]
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON body required"}), 400

        query = body.get("query")
        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "query must be a non-empty string"}), 400

        limit_raw = body.get("limit", config.max_matches)
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "limit must be an integer"}), 400

        try:
            result = run_discover(config, query.strip(), limit)
        except DiscoverError as exc:
            return jsonify({"error": str(exc)}), 400
        except DiscoverParseError as exc:
            return jsonify({"error": str(exc)}), 400
        except GlobLimitError as exc:
            return jsonify({"error": str(exc)}), 400
        except GlobTimeoutError as exc:
            return jsonify({"error": str(exc)}), 504
        except LlmDependencyError as exc:
            return jsonify({"error": str(exc)}), 503
        except LlmLoadError as exc:
            return jsonify({"error": str(exc)}), 503
        except LlmInferenceError as exc:
            return jsonify({"error": str(exc)}), 502
        except LlmError as exc:
            return jsonify({"error": str(exc)}), 503

        return jsonify(result.to_json_dict())
