"""Console scripts and scripts/ shims stay aligned (Phase D5)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Console name -> repo-relative shim path (when not maze.cli.<module>.py at scripts root).
SHIM_OVERRIDES: dict[str, str] = {
    "maze-langfuse-demo": "scripts/demos/langfuse_demo.py",
    "maze-kpms-fit": "scripts/kpms_fit.py",
    "maze-kpms-apply": "scripts/kpms_apply.py",
    "maze-daq": "",  # package __main__, no scripts/ shim
    "vast-daq": "",
    "maze-ram-daq": "",
    "maze-local-service": "",
}


def _load_pyproject_scripts() -> dict[str, str]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return dict(data["project"]["scripts"])


def _expected_shim(console_name: str, target: str) -> Path | None:
    if console_name in SHIM_OVERRIDES:
        rel = SHIM_OVERRIDES[console_name]
        return REPO_ROOT / rel if rel else None
    if not target.startswith("maze.cli."):
        return None
    module = target.split(":", 1)[0].removeprefix("maze.cli.")
    return SCRIPTS_DIR / f"{module}.py"


@pytest.mark.parametrize("console_name,target", sorted(_load_pyproject_scripts().items()))
def test_maze_cli_shim_exists(console_name: str, target: str) -> None:
    shim = _expected_shim(console_name, target)
    if shim is None:
        return
    assert shim.is_file(), f"missing shim for {console_name}: {shim.relative_to(REPO_ROOT)}"


@pytest.mark.parametrize("console_name,target", sorted(_load_pyproject_scripts().items()))
def test_entrypoint_importable(console_name: str, target: str) -> None:
    module_path, _, attr = target.partition(":")
    assert attr == "main", f"{console_name}: expected :main entry, got {target!r}"
    if module_path.startswith("maze.kpms."):
        pytest.importorskip("keypoint_moseq")
    if module_path == "maze.cli.langfuse_demo":
        pytest.importorskip("langfuse")
    mod = importlib.import_module(module_path)
    assert callable(getattr(mod, "main"))
