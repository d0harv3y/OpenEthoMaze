"""Portable path defaults (Phase A PR-A1, Phase D2 quarantine)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from maze.pipeline import paths as pipeline_paths
from maze.kpms import apply as kpms_apply
from maze.kpms.native_nor_results_paths import nor_native_group_to_h5_and_sleap

# Substrings that must not appear in library defaults (lab-specific roots).
_LAB_PATH_MARKERS = (
    "IMPRESS",
    r"E:\videos",
    r"E:\vast_analysis",
    "work sack",
    "impress data",
)

# Phase D2: kpMS path helpers + legacy/NOR/SLEAP CLIs tied to cohort discovery.
_D2_SOURCE_ROOTS = (
    Path("maze/kpms"),
    Path("maze/cli/legacy_db.py"),
    Path("maze/cli/generate_selected_trials_from_nor_kpms_results.py"),
    Path("maze/cli/sleap_nn_batch_inference.py"),
    Path("maze/cli/overlay_slp_bout_pipeline.py"),
)


def _path_text_has_lab_root(text: str) -> bool:
    normalized = text.replace("/", "\\")
    return any(marker in normalized for marker in _LAB_PATH_MARKERS)


@pytest.mark.parametrize(
    "value",
    [
        pipeline_paths.DEFAULT_DATA_DIR,
        pipeline_paths.DEFAULT_OUTPUT_H5,
        kpms_apply.DEFAULT_MANIFEST_CSV,
    ],
)
def test_default_paths_have_no_lab_hardcoded_roots(value: Path) -> None:
    text = str(value).replace("/", "\\")
    assert "IMPRESS" not in text
    assert r"E:\videos" not in text
    assert r"E:\vast_analysis" not in text


def test_repo_root_matches_package_layout(repo_root: Path) -> None:
    assert (repo_root / "maze" / "pipeline" / "paths.py").is_file()
    assert pipeline_paths.DEFAULT_OUTPUT_H5.is_relative_to(repo_root)
    assert kpms_apply.DEFAULT_MANIFEST_CSV.is_relative_to(repo_root)


def test_nor_native_group_requires_base_dir() -> None:
    sig = inspect.signature(nor_native_group_to_h5_and_sleap)
    base = sig.parameters["base_dir"]
    assert base.default is inspect.Parameter.empty


def test_nor_native_group_decode_roundtrip(tmp_path: Path) -> None:
    base = tmp_path / "nor"
    base.mkdir()
    (base / "standard format" / "exp1" / "3115").mkdir(parents=True)
    group = "D:-nor vids-standard format-exp1-3115-trial.h5"
    h5_p, slp_p = nor_native_group_to_h5_and_sleap(group, base_dir=base)
    assert h5_p == base / "standard format" / "exp1" / "3115" / "trial.h5"
    assert slp_p == Path(str(h5_p) + ".slp")


def test_d2_sources_have_no_lab_path_literals(repo_root: Path) -> None:
    offenders: list[str] = []
    for rel in _D2_SOURCE_ROOTS:
        path = repo_root / rel
        if path.is_dir():
            files = sorted(path.rglob("*.py"))
        else:
            files = [path]
        for py in files:
            text = py.read_text(encoding="utf-8")
            try:
                tree = ast.parse(text, filename=str(py))
            except SyntaxError:
                offenders.append(f"{py}: syntax error")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if _path_text_has_lab_root(node.value):
                        offenders.append(f"{py}:{node.lineno}: {node.value!r}")
    assert not offenders, "lab-specific path literals:\n" + "\n".join(offenders)
