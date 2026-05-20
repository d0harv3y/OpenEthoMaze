"""Unified localhost HTTP service (h5web + /orm/*). Phase B."""

from .config import (
    DEFAULT_GLOB_TIMEOUT_SECONDS,
    DEFAULT_HOST,
    DEFAULT_MAX_GLOBS,
    DEFAULT_MAX_MATCHES,
    DEFAULT_PORT,
    LocalServiceConfig,
    build_config,
)
from .glob_safe import GlobLimitError, GlobSafeError, GlobTimeoutError, glob_safe
from .sandbox import PathNotAllowedError, PathSandbox, PathSandboxError, SymlinkNotAllowedError

__all__ = [
    "DEFAULT_GLOB_TIMEOUT_SECONDS",
    "DEFAULT_HOST",
    "DEFAULT_MAX_GLOBS",
    "DEFAULT_MAX_MATCHES",
    "DEFAULT_PORT",
    "GlobLimitError",
    "GlobSafeError",
    "GlobTimeoutError",
    "LocalServiceConfig",
    "PathNotAllowedError",
    "PathSandbox",
    "PathSandboxError",
    "SymlinkNotAllowedError",
    "build_config",
    "glob_safe",
]
