"""Unit tests for maze.pipeline.run_provenance (Phase C7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maze.pipeline.run_provenance import (
    git_info,
    provenance_dir,
    provenance_run,
    record_provenance,
    sha256_file,
    write_provenance,
)


def test_git_info_in_repo(repo_root: Path) -> None:
    info = git_info(cwd=repo_root)
    if info["error"] is None:
        assert info["commit"] is not None
        assert len(info["commit"]) == 40
        assert isinstance(info["dirty"], bool)
    else:
        assert info["commit"] is None


def test_sha256_file_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "manifest.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    digest = sha256_file(p)
    assert digest is not None
    assert len(digest) == 64
    assert sha256_file(tmp_path / "missing.csv") is None


def test_write_provenance_creates_json(tmp_path: Path) -> None:
    anchor = tmp_path / "trials.h5"
    anchor.touch()
    path = write_provenance(
        anchor,
        {
            "schema_version": 1,
            "operation": "test_op",
            "started_at": "2026-05-21T12:00:00+00:00",
            "status": "ok",
            "inputs": {"db_path": str(anchor)},
        },
    )
    assert path.parent == provenance_dir(anchor)
    assert path.name.startswith("test_op_")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["operation"] == "test_op"
    assert data["inputs"]["db_path"] == str(anchor)


def test_provenance_run_success(tmp_path: Path) -> None:
    anchor = tmp_path / "results.h5"
    anchor.touch()
    with provenance_run("discovery_sync", anchor, {"n_dirs": 1}) as rec:
        rec["outputs"] = {"n_trials": 3}
    files = list(provenance_dir(anchor).glob("discovery_sync_*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["outputs"]["n_trials"] == 3
    assert "git" in payload


def test_provenance_run_failure_still_writes(tmp_path: Path) -> None:
    anchor = tmp_path / "trials.h5"
    anchor.touch()
    with pytest.raises(ValueError, match="boom"):
        with provenance_run("run_pipeline", anchor, {}):
            raise ValueError("boom")
    files = list(provenance_dir(anchor).glob("run_pipeline_*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert "boom" in payload["error"]


def test_record_provenance_one_shot(tmp_path: Path) -> None:
    anchor = tmp_path / "project"
    anchor.mkdir()
    path = record_provenance(
        anchor=anchor,
        operation="virtual_acquisition",
        inputs={"db_path": str(anchor / "trials.h5")},
        outputs={"n_ok": 2},
    )
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["operation"] == "virtual_acquisition"
    assert payload["outputs"]["n_ok"] == 2
