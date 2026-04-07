"""
Build and load a fixed kpMS exemplar trajectory table from **training** ``results.h5``.

Training coordinates are rebuilt from ``selected_trials.csv`` (same as fit) via
:class:`KpmsPreprocessConfig` and :func:`build_kpms_inputs` — matching
``maze.kpms.fit`` (no apply-stage confidence fragment filtering).

The overlay tray can load this HDF5 instead of recomputing typical trajectories
per trial on ``results_apply.h5``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ..core.anatomy import STANDARD_NODE_NAMES
from ..pipeline.io.file_discovery import TrialManifest, load_manifest_csv
from .preprocess import KpmsPreprocessConfig, build_kpms_inputs

_TRAINING_EXEMPLARS_VERSION = 1


@dataclass(frozen=True)
class TrainingExemplarBuildParams:
    """Parameters for :func:`exemplar_typical.typical_trajectories_for_exemplar_tray` (match overlay)."""

    pre_seconds: float = 0.167
    post_seconds: float = 0.5
    min_frequency: float = 0.003
    min_duration: int = 3
    density_sample: bool = True
    n_neighbors: int = 50
    fps: float = 30.0
    projection_plane: str = "xy"
    #: If True, match kpMS ``get_typical_trajectories`` (body-centered windows). If False, arena coords.
    egocentric: bool = False


def load_selected_trials_manifests(model_dir: Path) -> list[TrialManifest]:
    """Load trials from ``selected_trials.csv`` written during kpMS fit."""
    path = Path(model_dir) / "selected_trials.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing fit manifest: {path}")
    return load_manifest_csv(path)


def _recording_keys_with_syllables(results: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for k, v in results.items():
        if isinstance(v, dict) and "syllable" in v:
            out.append(str(k))
    return sorted(out)


def compute_training_typical_trajectories(
    *,
    results_h5: Path,
    manifests: list[TrialManifest],
    pre_cfg: KpmsPreprocessConfig,
    params: TrainingExemplarBuildParams,
) -> dict[int, np.ndarray]:
    """
    Rebuild training coordinates from manifests and run
    :func:`exemplar_typical.typical_trajectories_for_exemplar_tray` against training ``results.h5``.

    For each recording, coordinate time length must match the syllable vector (same ``T`` per key).
    Native kpMS fits on full videos need ``KpmsPreprocessConfig(retain_all_frames=True)``;
    ORM fit pipelines that fed filtered rows into the model should keep the default ``False``.
    """
    from keypoint_moseq.io import load_hdf5

    from .exemplar_typical import typical_trajectories_for_exemplar_tray

    results_all: dict[str, Any] = load_hdf5(str(results_h5))
    keys_results = set(_recording_keys_with_syllables(results_all))

    coordinates_full, _conf, _bp, skipped = build_kpms_inputs(manifests, pre_cfg)
    if not coordinates_full:
        raise RuntimeError(
            "No coordinates after build_kpms_inputs; check selected_trials.csv and sleap paths."
        )

    common = sorted(set(coordinates_full.keys()) & keys_results)
    if not common:
        raise RuntimeError(
            "No overlap between training results.h5 recording keys and build_kpms_inputs keys. "
            f"Example results keys: {sorted(keys_results)[:5]}, "
            f"example coord keys: {sorted(coordinates_full.keys())[:5]}, "
            f"skipped preprocess: {len(skipped)}"
        )

    coordinates = {k: coordinates_full[k] for k in common}
    results = {k: results_all[k] for k in common}

    pre = max(1, round(float(params.pre_seconds) * float(params.fps)))
    post = max(1, round(float(params.post_seconds) * float(params.fps)))

    typical = typical_trajectories_for_exemplar_tray(
        coordinates,
        results,
        pre=pre,
        post=post,
        min_frequency=float(params.min_frequency),
        min_duration=int(params.min_duration),
        bodyparts=list(STANDARD_NODE_NAMES),
        use_bodyparts=list(STANDARD_NODE_NAMES),
        density_sample=bool(params.density_sample),
        sampling_options={"n_neighbors": int(params.n_neighbors)},
        egocentric=bool(params.egocentric),
    )
    return {int(sid): np.asarray(arr, dtype=np.float64) for sid, arr in typical.items()}


def save_training_exemplar_table(
    path: Path,
    typical: dict[int, np.ndarray],
    *,
    source_results_h5: Path,
    pre_cfg: KpmsPreprocessConfig,
    params: TrainingExemplarBuildParams,
    extra_meta: dict[str, Any] | None = None,
) -> Path:
    """Write ``typical`` syllable trajectories to HDF5 (one dataset per syllable id)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    meta: dict[str, Any] = {
        "version": _TRAINING_EXEMPLARS_VERSION,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_results_h5": str(Path(source_results_h5).resolve()),
        "bodyparts": list(STANDARD_NODE_NAMES),
        "preprocess_config": {
            "min_fragment_frames": pre_cfg.min_fragment_frames,
            "jump_filter_cm": pre_cfg.jump_filter_cm,
            "jump_filter_lookahead_frames": pre_cfg.jump_filter_lookahead_frames,
            "px_per_cm": pre_cfg.px_per_cm,
        },
        "exemplar_params": {
            "pre_seconds": params.pre_seconds,
            "post_seconds": params.post_seconds,
            "min_frequency": params.min_frequency,
            "min_duration": params.min_duration,
            "density_sample": params.density_sample,
            "n_neighbors": params.n_neighbors,
            "fps": params.fps,
            "projection_plane": params.projection_plane,
            "egocentric": params.egocentric,
        },
    }
    if extra_meta:
        meta["extra"] = extra_meta

    import h5py

    with h5py.File(path, "w") as f:
        f.attrs["training_exemplars_json"] = json.dumps(meta, indent=2)
        g = f.create_group("syllables")
        for sid in sorted(typical.keys()):
            g.create_dataset(str(int(sid)), data=np.asarray(typical[sid], dtype=np.float64))
    return path


def load_training_exemplar_table_meta(path: Path) -> dict[str, Any]:
    import h5py

    with h5py.File(str(path), "r") as f:
        raw = f.attrs.get("training_exemplars_json", "{}")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        return json.loads(str(raw))


def load_training_exemplar_typical(
    path: Path, syllable_ids: list[int] | None = None
) -> dict[int, np.ndarray]:
    """
    Load stored (T, K, D) trajectories. If ``syllable_ids`` is set, only those ids
    are loaded (missing ids are skipped).
    """
    import h5py

    want = None if syllable_ids is None else {int(s) for s in syllable_ids if int(s) >= 0}
    out: dict[int, np.ndarray] = {}
    with h5py.File(str(path), "r") as f:
        if "syllables" not in f:
            return out
        g = f["syllables"]
        for name in g.keys():
            sid = int(name)
            if want is not None and sid not in want:
                continue
            out[sid] = np.asarray(g[name][:], dtype=np.float64)
    return out
