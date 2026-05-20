"""POST /orm/discover and discover planning (Phase B PR-B5).

Requires: core + dev (see ``fixtures.py``). Keyword fallback only in CI (no GGUF).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest_plugins = ["tests.controller.local_service.fixtures"]

from maze.controller.local_service.config import build_config
from maze.controller.local_service.discover import (
    DiscoverParseError,
    keyword_fallback_plan,
    parse_discover_json,
    run_discover,
)
from maze.controller.local_service.llm import LlmDependencyError, reset_llm_state


@pytest.fixture(autouse=True)
def _reset_llm() -> None:
    reset_llm_state()
    yield
    reset_llm_state()


def test_parse_discover_json_accepts_valid_plan() -> None:
    plan = parse_discover_json(
        json.dumps({"globs": ["**/*.h5", "**/*.csv"], "reason": "trial exports"})
    )
    assert plan.globs == ("**/*.h5", "**/*.csv")
    assert plan.reason == "trial exports"


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "{}",
        '{"globs": []}',
        '{"globs": ["../escape.h5"]}',
        '{"globs": [1]}',
    ],
)
def test_parse_discover_json_rejects_invalid(payload: str) -> None:
    with pytest.raises(DiscoverParseError):
        parse_discover_json(payload)


def test_keyword_fallback_includes_h5_patterns() -> None:
    plan = keyword_fallback_plan("find h5 trial files", max_globs=8)
    assert any("*.h5" in g for g in plan.globs)
    assert "keyword fallback" in plan.reason


def test_run_discover_keyword_mode_returns_sandboxed_paths(
    minimal_h5web_static: tuple[Path, Path],
) -> None:
    h5_base, _ = minimal_h5web_static
    config = build_config(h5_base)
    result = run_discover(config, "h5 trials", limit=50)

    assert result.mode == "keyword"
    assert (h5_base / "cohort" / "trials.h5").resolve() in {
        (h5_base / m).resolve() for m in result.matches
    }
    assert not any("secret.h5" in m for m in result.matches)


def test_post_orm_discover_llm_dependency_returns_503(
    local_app,
    minimal_h5web_static: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from maze.controller.local_service.app import create_local_app

    h5_base, static_dir = minimal_h5web_static
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"fake")
    config = build_config(h5_base, llm_model_path=gguf)
    app = create_local_app(config)
    client = app.test_client()

    def _raise_dep(_config: object, _query: str) -> str:
        raise LlmDependencyError("llama-cpp-python is not installed")

    import maze.controller.local_service.discover as discover_mod

    monkeypatch.setattr(discover_mod, "complete_discover_json", _raise_dep)
    monkeypatch.setattr(discover_mod, "is_llm_configured", lambda _c: True)
    monkeypatch.setattr(discover_mod, "configured_gguf_path", lambda _c: gguf)

    response = client.post("/orm/discover", json={"query": "trials", "limit": 10})
    assert response.status_code == 503
    assert "llama-cpp-python" in response.get_json()["error"]


@pytest.mark.llm_integration
def test_discover_llm_mode_when_gguf_available(
    minimal_h5web_static: tuple[Path, Path],
) -> None:
    """Optional: ``MAZE_LLM_GGUF`` + ``uv sync --extra local-service``."""
    gguf_env = os.environ.get("MAZE_LLM_GGUF", "").strip()
    if not gguf_env:
        pytest.skip("MAZE_LLM_GGUF not set (optional LLM integration test)")
    if not Path(gguf_env).is_file():
        pytest.skip(f"MAZE_LLM_GGUF file not found: {gguf_env}")

    try:
        import llama_cpp  # noqa: F401
    except ImportError:
        pytest.fail(
            "MAZE_LLM_GGUF is set but llama-cpp-python is not installed; "
            "run: uv sync --extra local-service"
        )

    h5_base, _ = minimal_h5web_static
    config = build_config(h5_base, llm_model_path=Path(gguf_env))
    result = run_discover(config, "h5 files", limit=10)
    assert result.mode == "llm"
    assert result.globs
