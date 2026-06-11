"""kpMS apply manifest chunking (GPU memory)."""

from __future__ import annotations

from maze.kpms.apply import _iter_manifest_chunks
from conftest import make_manifest


def test_iter_manifest_chunks_single_batch() -> None:
    manifests = [make_manifest(animal_id=str(i)) for i in range(5)]
    assert _iter_manifest_chunks(manifests, None) == [manifests]
    assert _iter_manifest_chunks(manifests, 0) == [manifests]
    assert _iter_manifest_chunks(manifests, 10) == [manifests]


def test_iter_manifest_chunks_splits() -> None:
    manifests = [make_manifest(animal_id=str(i)) for i in range(5)]
    chunks = _iter_manifest_chunks(manifests, 2)
    assert len(chunks) == 3
    assert [len(c) for c in chunks] == [2, 2, 1]
