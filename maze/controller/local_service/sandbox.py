"""Path sandbox for the local HTTP service (Phase B).

Symlink policy (v1): reject any symlink whose resolved target lies outside the
allowed root that contains the link. ``Path.resolve()`` alone is not trusted on
Windows lab drives where junctions/symlinks may point elsewhere.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

PathLike = Path | str


class PathSandboxError(ValueError):
    """Base error for sandbox violations."""


class PathNotAllowedError(PathSandboxError):
    """Path escapes allowed roots or uses forbidden ``..`` components."""


class SymlinkNotAllowedError(PathSandboxError):
    """Symlink resolves outside the containing allowed root."""


class PathSandbox:
    """Resolve user paths under one or more allowed directory roots."""

    def __init__(self, roots: Sequence[PathLike]) -> None:
        if not roots:
            raise ValueError("at least one allowed root is required")
        normalized: list[Path] = []
        for root in roots:
            resolved = Path(root).expanduser().resolve()
            if not resolved.is_dir():
                raise ValueError(f"allowed root must be an existing directory: {root}")
            normalized.append(resolved)
        self._roots: tuple[Path, ...] = tuple(normalized)

    @property
    def roots(self) -> tuple[Path, ...]:
        return self._roots

    def resolve(
        self,
        path: PathLike,
        *,
        base: Path | None = None,
        must_exist: bool = False,
    ) -> Path:
        """Resolve ``path`` under an allowed root.

        - Relative paths join ``base`` when given, otherwise the first root.
        - Absolute paths must still lie under an allowed root after resolution.
        - ``..`` components and symlinks escaping the root are rejected.
        """
        raw = Path(path)
        if any(part == ".." for part in raw.parts):
            raise PathNotAllowedError(f"path must not contain '..': {path}")

        if raw.is_absolute():
            candidate = raw
            containing_root = self._root_containing_or_none(candidate)
            if containing_root is None:
                raise PathNotAllowedError(f"path is outside allowed roots: {path}")
        else:
            anchor = base if base is not None else self._roots[0]
            if not self._is_under_any_root(anchor):
                raise PathNotAllowedError(f"base is outside allowed roots: {anchor}")
            containing_root = self._root_containing(anchor)
            candidate = anchor / raw

        resolved = self._resolve_under_root(containing_root, candidate, must_exist=must_exist)
        if not self._is_under_root(resolved, containing_root):
            raise PathNotAllowedError(f"resolved path escapes root: {path}")
        return resolved

    def _resolve_under_root(self, root: Path, path: Path, *, must_exist: bool) -> Path:
        """Walk ``path`` under ``root``, validating symlinks at each step."""
        root = root.resolve()
        if path.is_absolute():
            try:
                rel = path.resolve().relative_to(root)
            except ValueError as exc:
                raise PathNotAllowedError(f"path is outside allowed root {root}: {path}") from exc
        else:
            rel = path

        current = root
        for part in rel.parts:
            if part in (".", ""):
                continue
            if part == "..":
                raise PathNotAllowedError(f"path must not contain '..': {path}")

            next_path = current / part
            if next_path.is_symlink():
                link_target = next_path.readlink()
                if not link_target.is_absolute():
                    link_target = (next_path.parent / link_target)
                resolved_link = link_target.resolve()
                if not self._is_under_root(resolved_link, root):
                    raise SymlinkNotAllowedError(
                        f"symlink escapes allowed root {root}: {next_path} -> {resolved_link}"
                    )
                current = resolved_link
            else:
                current = next_path

        if must_exist and not current.exists():
            raise PathNotAllowedError(f"path does not exist: {path}")
        return current.resolve()

    def _root_containing(self, path: Path) -> Path:
        root = self._root_containing_or_none(path)
        if root is None:
            raise PathNotAllowedError(f"path is outside allowed roots: {path}")
        return root

    def _root_containing_or_none(self, path: Path) -> Path | None:
        resolved = path.expanduser().resolve()
        for root in self._roots:
            if self._is_under_root(resolved, root):
                return root
        return None

    def _is_under_any_root(self, path: Path) -> bool:
        return self._root_containing_or_none(path) is not None

    @staticmethod
    def _is_under_root(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def try_symlink(link_path: Path, target: Path) -> None:
        """Create a symlink for tests; raises ``OSError`` if unsupported."""
        link_path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "symlink"):
            os.symlink(str(target), str(link_path), target_is_directory=target.is_dir())
        else:
            raise OSError("os.symlink is not available")
