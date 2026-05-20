"""Configuration for the unified local HTTP service (Phase B)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .sandbox import PathSandbox

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MAX_GLOBS = 16
DEFAULT_MAX_MATCHES = 200
DEFAULT_GLOB_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class LocalServiceConfig:
    """Sandbox and resource limits for ``maze-local-service``."""

    data_root: Path
    extra_roots: tuple[Path, ...] = ()
    max_globs: int = DEFAULT_MAX_GLOBS
    max_matches: int = DEFAULT_MAX_MATCHES
    glob_timeout_seconds: float = DEFAULT_GLOB_TIMEOUT_SECONDS
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    llm_model_path: Path | None = None

    def __post_init__(self) -> None:
        if self.max_globs < 1:
            raise ValueError("max_globs must be >= 1")
        if self.max_matches < 1:
            raise ValueError("max_matches must be >= 1")
        if self.glob_timeout_seconds <= 0:
            raise ValueError("glob_timeout_seconds must be > 0")
        if not self.host.strip():
            raise ValueError("host must be non-empty")
        if self.port < 1 or self.port > 65535:
            raise ValueError("port must be in 1..65535")

    @property
    def allowed_roots(self) -> tuple[Path, ...]:
        return (self.data_root, *self.extra_roots)

    def sandbox(self) -> PathSandbox:
        """Build a :class:`PathSandbox` from configured roots."""
        return PathSandbox(self.allowed_roots)


def build_config(
    data_root: Path | str,
    *,
    extra_roots: Sequence[Path | str] = (),
    max_globs: int = DEFAULT_MAX_GLOBS,
    max_matches: int = DEFAULT_MAX_MATCHES,
    glob_timeout_seconds: float = DEFAULT_GLOB_TIMEOUT_SECONDS,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    llm_model_path: Path | str | None = None,
    require_existing_roots: bool = True,
) -> LocalServiceConfig:
    """Normalize paths and return a validated :class:`LocalServiceConfig`."""
    roots = [_normalize_root(Path(data_root), require_existing=require_existing_roots)]
    for raw in extra_roots:
        roots.append(_normalize_root(Path(raw), require_existing=require_existing_roots))
    data = roots[0]
    extras = tuple(roots[1:])
    llm_path = _normalize_optional_gguf(llm_model_path)
    return LocalServiceConfig(
        data_root=data,
        extra_roots=extras,
        max_globs=max_globs,
        max_matches=max_matches,
        glob_timeout_seconds=glob_timeout_seconds,
        host=host,
        port=port,
        llm_model_path=llm_path,
    )


def _normalize_optional_gguf(path: Path | str | None) -> Path | None:
    if path is None or (isinstance(path, str) and not path.strip()):
        return None
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"GGUF model file not found: {path}")
    return resolved


def _normalize_root(path: Path, *, require_existing: bool) -> Path:
    resolved = path.expanduser().resolve()
    if require_existing and not resolved.is_dir():
        raise ValueError(f"root must be an existing directory: {path}")
    return resolved
