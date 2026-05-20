"""Optional llama-cpp-python GGUF backend for /orm/discover (Phase B5).

When ``MAZE_LLM_GGUF`` / ``--llm-model`` is unset, discover uses keyword/glob
fallback (see ``discover.py``) so CI and lean installs need no GGUF.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import LocalServiceConfig

_LLM_INSTANCE: object | None = None
_LLM_LOADED_PATH: Path | None = None


class LlmError(Exception):
    """Base error for LLM loading or inference."""


class LlmNotConfiguredError(LlmError):
    """No GGUF path configured."""


class LlmDependencyError(LlmError):
    """llama-cpp-python missing (``local-service`` extra)."""


class LlmLoadError(LlmError):
    """GGUF path invalid or model failed to load."""


class LlmInferenceError(LlmError):
    """Model call failed."""


def configured_gguf_path(config: LocalServiceConfig) -> Path | None:
    """Resolved GGUF path from config or ``MAZE_LLM_GGUF`` env."""
    if config.llm_model_path is not None:
        return config.llm_model_path
    raw = os.environ.get("MAZE_LLM_GGUF", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if path.is_file() else None


def is_llm_configured(config: LocalServiceConfig) -> bool:
    return configured_gguf_path(config) is not None


def is_llm_loaded() -> bool:
    return _LLM_INSTANCE is not None


def reset_llm_state() -> None:
    """Clear cached model (tests only)."""
    global _LLM_INSTANCE, _LLM_LOADED_PATH
    _LLM_INSTANCE = None
    _LLM_LOADED_PATH = None


def load_llm(config: LocalServiceConfig) -> None:
    """Load GGUF once; requires ``uv sync --extra local-service``."""
    global _LLM_INSTANCE, _LLM_LOADED_PATH

    path = configured_gguf_path(config)
    if path is None:
        raise LlmNotConfiguredError(
            "LLM not configured (set MAZE_LLM_GGUF or pass --llm-model)"
        )
    if _LLM_INSTANCE is not None and _LLM_LOADED_PATH == path:
        return

    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise LlmDependencyError(
            "llama-cpp-python is not installed; run: uv sync --extra local-service"
        ) from exc

    try:
        _LLM_INSTANCE = Llama(model_path=str(path), verbose=False)
    except Exception as exc:
        raise LlmLoadError(f"failed to load GGUF at {path}: {exc}") from exc
    _LLM_LOADED_PATH = path


def complete_discover_json(config: LocalServiceConfig, query: str) -> str:
    """Return raw model text constrained to a discover JSON object."""
    if _LLM_INSTANCE is None:
        load_llm(config)

    prompt = (
        "You help find files under a lab data directory. "
        "Respond with JSON only, no markdown, matching this schema:\n"
        '{"globs": ["**/*.h5"], "reason": "short explanation"}\n'
        "Use pathlib glob patterns relative to the data root. "
        "No '..' segments. At most 16 patterns.\n"
        f"User request: {query.strip()}\n"
    )
    assert _LLM_INSTANCE is not None
    try:
        out = _LLM_INSTANCE.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.1,
        )
    except Exception as exc:
        raise LlmInferenceError(f"LLM inference failed: {exc}") from exc

    choices = out.get("choices") or []
    if not choices:
        raise LlmInferenceError("LLM returned no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LlmInferenceError("LLM returned empty content")
    return content.strip()


def extract_json_object(text: str) -> str:
    """Strip optional markdown fences and return a JSON object substring."""
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped, re.IGNORECASE)
    if fence:
        stripped = fence.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LlmInferenceError("LLM response did not contain a JSON object")
    return stripped[start : end + 1]
