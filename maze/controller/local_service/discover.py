"""Discover planning and sandboxed glob execution (Phase B5).

Discover mode (v1):
- **keyword** — default when no GGUF is configured (CI / ``uv sync --extra dev``).
- **llm** — when ``MAZE_LLM_GGUF`` or ``--llm-model`` points at a file and
  ``llama-cpp-python`` is installed (``local-service`` extra).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .glob_safe import GlobSafeError, glob_safe
from .llm import (
    LlmDependencyError,
    LlmInferenceError,
    LlmLoadError,
    LlmNotConfiguredError,
    complete_discover_json,
    configured_gguf_path,
    extract_json_object,
    is_llm_configured,
)

if TYPE_CHECKING:
    from .config import LocalServiceConfig

DiscoverMode = str  # "keyword" | "llm"


class DiscoverError(ValueError):
    """Invalid discover request or plan."""


class DiscoverParseError(DiscoverError):
    """LLM JSON did not match the discover schema."""


@dataclass(frozen=True)
class DiscoverPlan:
    globs: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class DiscoverResult:
    query: str
    mode: DiscoverMode
    globs: tuple[str, ...]
    reason: str
    matches: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "mode": self.mode,
            "globs": list(self.globs),
            "reason": self.reason,
            "matches": list(self.matches),
        }


def parse_discover_json(text: str) -> DiscoverPlan:
    """Validate LLM output: ``{"globs": ["**/*.h5", ...], "reason": "..."}``."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DiscoverParseError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DiscoverParseError("discover JSON must be an object")
    globs_raw = data.get("globs")
    if not isinstance(globs_raw, list) or not globs_raw:
        raise DiscoverParseError("globs must be a non-empty list of strings")
    globs: list[str] = []
    for item in globs_raw:
        if not isinstance(item, str) or not item.strip():
            raise DiscoverParseError("each glob must be a non-empty string")
        pattern = item.strip().replace("\\", "/")
        if ".." in pattern:
            raise DiscoverParseError(f"glob must not contain '..': {pattern!r}")
        globs.append(pattern)
    reason_raw = data.get("reason", "")
    reason = str(reason_raw).strip() if reason_raw is not None else ""
    return DiscoverPlan(globs=tuple(globs), reason=reason)


def keyword_fallback_plan(query: str, *, max_globs: int) -> DiscoverPlan:
    """Non-LLM glob plan from query keywords (used when no GGUF is configured)."""
    q = query.lower().strip()
    globs: list[str] = []
    if "h5" in q or "hdf5" in q or "hdf" in q:
        globs.append("**/*.h5")
    if "slp" in q or "sleap" in q:
        globs.extend(["**/*.slp", "**/*.h5.slp"])
    if "csv" in q:
        globs.append("**/*.csv")
    if "mp4" in q or "video" in q:
        globs.append("**/*.mp4")
    if not globs:
        for token in q.split():
            cleaned = "".join(c for c in token if c.isalnum() or c in "._-*")
            if len(cleaned) >= 2:
                globs.append(f"**/*{cleaned}*")
    if not globs:
        globs.append("**/*.h5")
    unique = list(dict.fromkeys(globs))
    capped = unique[:max_globs]
    return DiscoverPlan(
        globs=tuple(capped),
        reason="keyword fallback (no GGUF model configured)",
    )


def plan_discover(config: LocalServiceConfig, query: str) -> tuple[DiscoverPlan, DiscoverMode]:
    """Choose glob plan via LLM (if configured) or keyword fallback."""
    if is_llm_configured(config):
        path = configured_gguf_path(config)
        assert path is not None
        try:
            raw = complete_discover_json(config, query)
            plan = parse_discover_json(extract_json_object(raw))
            return _cap_plan(plan, config.max_globs), "llm"
        except LlmNotConfiguredError:
            pass
        except (LlmDependencyError, LlmLoadError, LlmInferenceError):
            raise
        except DiscoverParseError:
            raise
    return keyword_fallback_plan(query, max_globs=config.max_globs), "keyword"


def run_discover(config: LocalServiceConfig, query: str, limit: int) -> DiscoverResult:
    """Plan globs and return sandboxed match paths (relative to ``data_root`` when possible)."""
    if not query.strip():
        raise DiscoverError("query must be non-empty")
    if limit < 1:
        raise DiscoverError("limit must be >= 1")

    effective_limit = min(limit, config.max_matches)
    plan, mode = plan_discover(config, query)
    sandbox = config.sandbox()
    try:
        paths = glob_safe(
            sandbox,
            plan.globs,
            max_globs=config.max_globs,
            max_matches=effective_limit,
            timeout_seconds=config.glob_timeout_seconds,
        )
    except GlobSafeError:
        raise

    matches = tuple(
        _display_path(p, config.data_root) for p in sorted(paths, key=lambda x: str(x))
    )
    return DiscoverResult(
        query=query,
        mode=mode,
        globs=plan.globs,
        reason=plan.reason,
        matches=matches,
    )


def _cap_plan(plan: DiscoverPlan, max_globs: int) -> DiscoverPlan:
    if len(plan.globs) <= max_globs:
        return plan
    return DiscoverPlan(globs=plan.globs[:max_globs], reason=plan.reason)


def _display_path(path: Path, data_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(data_root.resolve()))
    except ValueError:
        return str(path)
