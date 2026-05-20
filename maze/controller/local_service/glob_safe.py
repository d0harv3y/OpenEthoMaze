"""Sandboxed glob execution for /orm/discover (Phase B).

Patterns are evaluated relative to each allowed root. Only paths that pass
:class:`~maze.controller.local_service.sandbox.PathSandbox` resolution are returned.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Sequence

from .sandbox import PathSandbox, PathSandboxError


class GlobSafeError(ValueError):
    """Base error for glob_safe violations."""


class GlobLimitError(GlobSafeError):
    """glob pattern or match cap exceeded."""


class GlobTimeoutError(GlobSafeError):
    """Wall-clock timeout while scanning."""


def glob_safe(
    sandbox: PathSandbox,
    patterns: Sequence[str],
    *,
    max_globs: int,
    max_matches: int,
    timeout_seconds: float,
) -> list[Path]:
    """Return unique paths under ``sandbox.roots`` matching ``patterns``.

    Raises:
        GlobLimitError: too many patterns, matches, or forbidden ``..`` in a pattern.
        GlobTimeoutError: exceeded ``timeout_seconds``.
        PathNotAllowedError: a match resolves outside allowed roots.
    """
    if max_globs < 1 or max_matches < 1 or timeout_seconds <= 0:
        raise ValueError("max_globs, max_matches must be >= 1 and timeout_seconds > 0")

    if len(patterns) > max_globs:
        raise GlobLimitError(f"at most {max_globs} glob patterns allowed, got {len(patterns)}")

    deadline = time.monotonic() + timeout_seconds
    seen: set[Path] = set()
    results: list[Path] = []

    for pattern in patterns:
        _check_deadline(deadline)
        if ".." in pattern.replace("\\", "/"):
            raise GlobLimitError(f"glob pattern must not contain '..': {pattern!r}")

        for root in sandbox.roots:
            _check_deadline(deadline)
            iterator = root.glob(pattern)
            for match in iterator:
                _check_deadline(deadline)
                if not match.is_file() and not match.is_dir():
                    continue
                try:
                    resolved = sandbox.resolve(match, must_exist=True)
                except PathSandboxError:
                    continue
                if resolved in seen:
                    continue
                seen.add(resolved)
                results.append(resolved)
                if len(results) >= max_matches:
                    raise GlobLimitError(f"match cap {max_matches} exceeded")
    return results


def _check_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise GlobTimeoutError("glob scan exceeded wall-clock timeout")
