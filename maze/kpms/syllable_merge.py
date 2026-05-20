"""
Semantic syllable merge via keypoint-moseq (user-defined groups), with metadata sidecars.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SyllableMergeSpec:
    """Groups of raw syllable ids to merge (each inner list becomes one new id after mapping)."""

    groups: list[list[int]]

    @staticmethod
    def from_mapping(data: dict[str, Any]) -> "SyllableMergeSpec":
        raw = data.get("groups")
        if not isinstance(raw, list) or not raw:
            raise ValueError("Merge spec must contain non-empty 'groups' list")
        groups: list[list[int]] = []
        for g in raw:
            if not isinstance(g, list) or not g:
                raise ValueError("Each group must be a non-empty list of integers")
            groups.append([int(x) for x in g])
        return SyllableMergeSpec(groups=groups)


def load_merge_spec(path: Path | str) -> SyllableMergeSpec:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    data = _parse_yaml_or_json(text)
    return SyllableMergeSpec.from_mapping(data)


def _parse_yaml_or_json(text: str) -> dict[str, Any]:
    import json

    try:
        out = json.loads(text)
        if isinstance(out, dict):
            return out
    except json.JSONDecodeError:
        pass
    try:
        import yaml

        loaded = yaml.safe_load(text)
    except ImportError as e:
        raise RuntimeError("Install pyyaml (uv sync --extra kpms) or use JSON merge spec") from e
    if not isinstance(loaded, dict):
        raise ValueError("Merge spec root must be a mapping")
    return loaded


def apply_merge_to_results(
    results: dict[str, Any],
    spec: SyllableMergeSpec,
) -> tuple[dict[str, Any], dict[int, int]]:
    """Return new results dict and old->new syllable index mapping."""
    import keypoint_moseq as kpms

    mapping = kpms.generate_syllable_mapping(results, spec.groups)
    # Preserve common sentinel if present in streams
    if any(int(x) == -1 for res in results.values() for x in res.get("syllable", ())):
        mapping = dict(mapping)
        mapping[-1] = -1
    new_results = kpms.apply_syllable_mapping(results, mapping)
    return new_results, mapping


def save_merged_results_h5(
    out_path: Path,
    new_results: dict[str, Any],
    *,
    source_h5: Path,
    spec: SyllableMergeSpec,
    mapping: dict[int, int],
    extra_meta: dict[str, Any] | None = None,
) -> Path:
    """Write merged results with HDF5 attrs (json sidecar with full metadata)."""
    from keypoint_moseq.io import save_hdf5

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.is_file():
        out_path.unlink()

    save_hdf5(str(out_path), new_results, exist_ok=True, overwrite=True)

    meta: dict[str, Any] = {
        "kind": "syllable_merge",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_results_h5": str(Path(source_h5).resolve()),
        "groups": spec.groups,
        "mapping": {str(k): int(v) for k, v in sorted(mapping.items())},
    }
    if extra_meta:
        meta["extra"] = extra_meta

    sidecar = out_path.with_suffix(out_path.suffix + ".merge_meta.json")
    sidecar.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    raw = json.dumps(meta, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:16]
    try:
        import h5py

        with h5py.File(str(out_path), "a") as f:
            f.attrs["orm_syllable_merge_json"] = json.dumps(meta, indent=2)
            f.attrs["orm_syllable_merge_sha256_16"] = digest
    except OSError:
        pass

    return out_path
