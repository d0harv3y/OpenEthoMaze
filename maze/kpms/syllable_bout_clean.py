"""
Pluggable post-hoc cleanup for discrete syllable label sequences (after semantic merge).

Steps are pure transforms on ``z[int]`` (per-frame syllable ids). Compose via YAML/JSON
or named presets. See :mod:`maze.kpms.syllable_merge` for taxonomy merge (kpMS API).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict

import numpy as np

OrphanPolicy = Literal["previous", "next", "neg1"]
GapPolicy = Literal["noise_only", "max_distinct"]


class StepDict(TypedDict, total=False):
    type: str
    min_bout_s: float
    orphan_policy: str
    max_gap_s: float
    gap_policy: str
    noise_labels: list[int]
    max_distinct: int


@dataclass(frozen=True)
class DropShortRuns:
    """Remove runs shorter than ``min_bout_s`` (orphan frames relabeled)."""

    min_bout_s: float
    orphan_policy: OrphanPolicy = "previous"

    def apply(self, z: np.ndarray, fps: float) -> np.ndarray:
        z = np.asarray(z, dtype=np.int64).copy()
        n = len(z)
        if n == 0:
            return z
        min_frames = max(1, int(round(float(self.min_bout_s) * float(fps))))
        runs = _runs_rle(z)
        for lab, start, end in runs:
            if end - start >= min_frames:
                continue
            lo = start
            hi = end
            fill = _orphan_fill(z, lo, hi, self.orphan_policy)
            z[lo:hi] = fill
        return z.astype(np.int64)


@dataclass(frozen=True)
class BridgeSameLabel:
    """
    Bridge gaps between two runs of the same label **k** when the gap is short
    and passes ``gap_policy``.

    Only **one** intervening run (RLE segment) between matching **k** runs is
    considered per pass; the transform repeats until stable (so chained gaps
    can be resolved in multiple iterations).
    """

    max_gap_s: float
    gap_policy: GapPolicy = "noise_only"
    noise_labels: frozenset[int] = field(default_factory=frozenset)
    max_distinct: int = 0

    def apply(self, z: np.ndarray, fps: float) -> np.ndarray:
        z = np.asarray(z, dtype=np.int64).copy()
        n = len(z)
        if n < 3:
            return z
        max_gap = max(0, int(round(float(self.max_gap_s) * float(fps))))
        if max_gap <= 0:
            return z

        changed = True
        while changed:
            changed = False
            runs = _runs_rle(z)
            for i in range(len(runs) - 2):
                lab_l, s_l, e_l = runs[i]
                lab_m, s_m, e_m = runs[i + 1]
                lab_r, s_r, e_r = runs[i + 2]
                if lab_l != lab_r or lab_l == lab_m:
                    continue
                gap_len = e_m - s_m
                if gap_len > max_gap:
                    continue
                gap_slice = z[s_m:e_m]
                if not self._gap_ok(lab_l, gap_slice):
                    continue
                z[s_m:e_m] = lab_l
                changed = True
                break
        return z.astype(np.int64)

    def _gap_ok(self, k: int, gap_slice: np.ndarray) -> bool:
        if self.gap_policy == "noise_only":
            noise = self.noise_labels
            for v in gap_slice:
                if int(v) == int(k):
                    return False
                if int(v) not in noise:
                    return False
            return len(gap_slice) > 0
        if self.gap_policy == "max_distinct":
            uniq = {int(v) for v in gap_slice}
            uniq.discard(int(k))
            return len(uniq) <= int(self.max_distinct)
        return False


def _runs_rle(z: np.ndarray) -> list[tuple[int, int, int]]:
    """Return list of (label, start, end_exclusive) for contiguous runs."""
    z = np.asarray(z, dtype=np.int64).ravel()
    n = len(z)
    if n == 0:
        return []
    out: list[tuple[int, int, int]] = []
    i0 = 0
    cur = int(z[0])
    for i in range(1, n):
        if int(z[i]) != cur:
            out.append((cur, i0, i))
            i0 = i
            cur = int(z[i])
    out.append((cur, i0, n))
    return out


def _orphan_fill(z: np.ndarray, start: int, end: int, policy: OrphanPolicy) -> int:
    n = len(z)
    if policy == "neg1":
        return -1
    if policy == "previous":
        if start > 0:
            return int(z[start - 1])
        if end < n:
            return int(z[end])
        return -1
    if policy == "next":
        if end < n:
            return int(z[end])
        if start > 0:
            return int(z[start - 1])
        return -1
    return -1


BoutStep = DropShortRuns | BridgeSameLabel


def expand_preset(name: str) -> list[BoutStep]:
    """Named step lists (mirrors movement-bout style defaults where applicable)."""
    from ..pipeline.defaults import MIN_MOVEMENT_BOUT_DURATION_S, MOVEMENT_INTER_BOUT_INTERVAL_S

    n = str(name).strip().lower()
    if n in ("conservative", "drop_only"):
        return [
            DropShortRuns(min_bout_s=float(MIN_MOVEMENT_BOUT_DURATION_S), orphan_policy="previous"),
        ]
    if n in ("movement_like", "movement-like"):
        return [
            DropShortRuns(min_bout_s=float(MIN_MOVEMENT_BOUT_DURATION_S), orphan_policy="previous"),
            BridgeSameLabel(
                max_gap_s=float(MOVEMENT_INTER_BOUT_INTERVAL_S),
                gap_policy="noise_only",
                noise_labels=frozenset(),
            ),
        ]
    raise ValueError(f"Unknown bout cleanup preset: {name!r}")


def steps_from_dicts(raw: list[dict[str, Any]]) -> list[BoutStep]:
    out: list[BoutStep] = []
    for d in raw:
        t = str(d.get("type", "")).strip().lower()
        if t in ("drop_short_runs", "drop_short"):
            out.append(
                DropShortRuns(
                    min_bout_s=float(d["min_bout_s"]),
                    orphan_policy=str(d.get("orphan_policy", "previous")),  # type: ignore[arg-type]
                )
            )
        elif t in ("bridge_same_label", "bridge"):
            gp = str(d.get("gap_policy", "noise_only")).strip().lower()
            if gp not in ("noise_only", "max_distinct"):
                raise ValueError(f"Unsupported gap_policy: {gp!r}")
            noise = d.get("noise_labels") or []
            out.append(
                BridgeSameLabel(
                    max_gap_s=float(d["max_gap_s"]),
                    gap_policy=gp,  # type: ignore[arg-type]
                    noise_labels=frozenset(int(x) for x in noise),
                    max_distinct=int(d.get("max_distinct", 0)),
                )
            )
        else:
            raise ValueError(f"Unknown bout step type: {t!r}")
    return out


def apply_syllable_bout_pipeline(
    z: np.ndarray,
    *,
    fps: float,
    steps: list[BoutStep],
) -> np.ndarray:
    """Apply ordered bout cleanup steps."""
    x = np.asarray(z, dtype=np.int64).copy()
    for st in steps:
        x = st.apply(x, fps=float(fps))
    return x.astype(np.int64)


def apply_bout_pipeline_to_results(
    results: dict[str, Any],
    *,
    fps: float,
    steps: list[BoutStep],
) -> dict[str, Any]:
    """Apply bout cleanup to every ``syllable`` vector in a kpMS-style results dict."""
    out: dict[str, Any] = {}
    for k, v in results.items():
        if not isinstance(v, dict) or "syllable" not in v:
            out[k] = v
            continue
        nv = dict(v)
        nv["syllable"] = apply_syllable_bout_pipeline(
            np.asarray(v["syllable"]), fps=fps, steps=steps
        )
        out[k] = nv
    return out


def save_bout_cleaned_results_h5(
    out_path: Path,
    new_results: dict[str, Any],
    *,
    source_h5: Path,
    steps: list[BoutStep],
    fps: float,
    config_path: Path | None,
    preset: str | None,
) -> Path:
    """Write bout-cleaned results and a JSON sidecar with step metadata."""
    import json
    from datetime import datetime, timezone

    from keypoint_moseq.io import save_hdf5

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.is_file():
        out_path.unlink()

    save_hdf5(str(out_path), new_results, exist_ok=True, overwrite=True)

    meta: dict[str, Any] = {
        "kind": "syllable_bout_clean",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_results_h5": str(Path(source_h5).resolve()),
        "fps": float(fps),
        "preset": preset,
        "config_path": str(config_path) if config_path else None,
        "steps": [_step_to_dict(s) for s in steps],
    }
    sidecar = out_path.with_suffix(out_path.suffix + ".bout_clean_meta.json")
    sidecar.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    try:
        import h5py

        with h5py.File(str(out_path), "a") as f:
            f.attrs["orm_syllable_bout_clean_json"] = json.dumps(meta, indent=2)
    except OSError:
        pass

    return out_path


def _step_to_dict(st: BoutStep) -> dict[str, Any]:
    if isinstance(st, DropShortRuns):
        return {
            "type": "drop_short_runs",
            "min_bout_s": st.min_bout_s,
            "orphan_policy": st.orphan_policy,
        }
    if isinstance(st, BridgeSameLabel):
        return {
            "type": "bridge_same_label",
            "max_gap_s": st.max_gap_s,
            "gap_policy": st.gap_policy,
            "noise_labels": sorted(st.noise_labels),
            "max_distinct": st.max_distinct,
        }
    return {"type": type(st).__name__}


def load_pipeline_config(path: str | Any) -> tuple[list[BoutStep], float]:
    """
    Load YAML/JSON with optional ``preset`` or explicit ``steps`` and ``fps``.
    """
    if isinstance(path, (str, Path)):
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        data = _parse_yaml_or_json(text)
    else:
        data = dict(path)

    fps = float(data.get("fps", 30.0))
    if "preset" in data and data["preset"]:
        steps = expand_preset(str(data["preset"]))
    elif "steps" in data:
        steps = steps_from_dicts(list(data["steps"]))
    else:
        raise ValueError("Config must include 'preset' or 'steps'")
    return steps, fps


def _parse_yaml_or_json(text: str) -> dict[str, Any]:
    import json

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        import yaml

        loaded = yaml.safe_load(text)
    except ImportError as e:
        raise RuntimeError("Install pyyaml (uv sync --extra kpms) or use JSON config") from e
    if not isinstance(loaded, dict):
        raise ValueError("Config root must be a mapping")
    return loaded
