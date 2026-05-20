"""
Orchestrate keypoint-moseq review outputs (grid movies, trajectory plots, similarity matrix).

Requires ``uv sync --extra kpms``.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np

from ..core.anatomy import SKELETON_EDGES, STANDARD_NODE_NAMES
from ..pipeline.io.file_discovery import TrialManifest
from .preprocess import KpmsPreprocessConfig, build_kpms_inputs


def recording_keys_with_syllables(results: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for k, v in results.items():
        if isinstance(v, dict) and "syllable" in v:
            out.append(str(k))
    return sorted(out)


def align_coordinates_results(
    coordinates: dict[str, np.ndarray],
    confidences: dict[str, np.ndarray],
    results: dict[str, Any],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, Any]]:
    """Keep only recordings present in both coordinates and results (syllable-bearing)."""
    keys_results = set(recording_keys_with_syllables(results))
    common = sorted(set(coordinates.keys()) & keys_results)
    coord = {k: coordinates[k] for k in common}
    conf = {k: confidences[k] for k in common if k in confidences}
    res = {k: results[k] for k in common}
    return coord, conf, res


def video_paths_for_results(
    manifests: list[TrialManifest], result_keys: list[str]
) -> dict[str, str]:
    """Map kpMS recording key -> video file path (existing files only)."""
    by_kpms: dict[str, TrialManifest] = {}
    for m in manifests:
        by_kpms[m.kpms_results_dict_key] = m
    out: dict[str, str] = {}
    for k in result_keys:
        m = by_kpms.get(k)
        if m is None or not m.video_path:
            continue
        p = Path(m.video_path)
        if p.is_file():
            out[k] = str(p.resolve())
    return out


def run_similarity_matrix_csv(
    coordinates: dict[str, np.ndarray],
    results: dict[str, Any],
    out_csv: Path,
    *,
    metric: str = "cosine",
    pre: int = 5,
    post: int = 15,
    min_frequency: float = 0.005,
    min_duration: int = 3,
    density_sample: bool = False,
    sampling_options: dict[str, Any] | None = None,
) -> Path:
    """Write pairwise syllable trajectory distances (kpMS ``syllable_similarity``)."""
    import keypoint_moseq as kpms

    so = sampling_options if sampling_options is not None else {"n_neighbors": 50}
    distances, syllable_ixs = kpms.syllable_similarity(
        coordinates,
        results,
        metric=metric,
        pre=pre,
        post=post,
        min_frequency=min_frequency,
        min_duration=min_duration,
        bodyparts=list(STANDARD_NODE_NAMES),
        use_bodyparts=list(STANDARD_NODE_NAMES),
        density_sample=density_sample,
        sampling_options=so,
    )
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    labels = [str(int(s)) for s in syllable_ixs]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["syllable"] + labels)
        for i, row in enumerate(distances):
            w.writerow([labels[i]] + [float(x) for x in row])
    return out_csv


def run_grid_movies(
    coordinates: dict[str, np.ndarray],
    results: dict[str, Any],
    *,
    project_dir: str | None,
    model_name: str | None,
    output_dir: Path,
    video_paths: dict[str, str] | None,
    keypoints_only: bool,
    fps: float,
    min_frequency: float,
    min_duration: int,
    sampling_options: dict[str, Any],
) -> None:
    import keypoint_moseq as kpms

    skeleton_edges = [list(e) for e in SKELETON_EDGES]
    kwargs: dict[str, Any] = dict(
        results=results,
        project_dir=project_dir,
        model_name=model_name,
        output_dir=str(output_dir),
        coordinates=coordinates,
        bodyparts=list(STANDARD_NODE_NAMES),
        use_bodyparts=list(STANDARD_NODE_NAMES),
        fps=fps,
        min_frequency=min_frequency,
        min_duration=min_duration,
        sampling_options=sampling_options,
        skeleton=skeleton_edges,
        keypoints_only=keypoints_only,
    )
    if video_paths:
        kwargs["video_paths"] = video_paths
    kpms.generate_grid_movies(**kwargs)


def run_trajectory_plots(
    coordinates: dict[str, np.ndarray],
    results: dict[str, Any],
    *,
    project_dir: str | None,
    model_name: str | None,
    output_dir: Path,
    fps: float,
    min_frequency: float,
    min_duration: int,
    save_gifs: bool,
    save_mp4s: bool,
    interactive: bool,
    density_sample: bool,
    sampling_options: dict[str, Any],
) -> None:
    import keypoint_moseq as kpms

    skeleton_edges = [list(e) for e in SKELETON_EDGES]
    kpms.generate_trajectory_plots(
        coordinates,
        results,
        project_dir=project_dir,
        model_name=model_name,
        output_dir=str(output_dir),
        bodyparts=list(STANDARD_NODE_NAMES),
        use_bodyparts=list(STANDARD_NODE_NAMES),
        skeleton=skeleton_edges,
        fps=fps,
        min_frequency=min_frequency,
        min_duration=min_duration,
        save_gifs=save_gifs,
        save_mp4s=save_mp4s,
        interactive=interactive,
        density_sample=density_sample,
        sampling_options=sampling_options,
    )


def write_review_readme(
    out_dir: Path,
    *,
    grid_dir: Path | None,
    traj_dir: Path | None,
    similarity_csv: Path | None,
    results_h5: Path,
    n_recordings: int,
) -> Path:
    """Write a short index of generated artifacts."""
    lines = [
        "# kpMS review artifacts",
        "",
        f"- **Source results:** `{results_h5}`",
        f"- **Recordings used:** {n_recordings}",
        "",
    ]
    if grid_dir is not None:
        lines.append(f"- **Grid movies:** `{grid_dir}`")
    if traj_dir is not None:
        lines.append(f"- **Trajectory plots / GIFs:** `{traj_dir}`")
    if similarity_csv is not None:
        lines.append(f"- **Syllable similarity matrix (CSV):** `{similarity_csv}`")
    lines.extend(
        [
            "",
            "Use the merge spec + `kpms_apply_syllable_merge.py` after deciding groups,",
            "then `kpms_clean_syllable_bouts.py` for temporal cleanup.",
        ]
    )
    p = Path(out_dir) / "README_review.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def build_coordinates_for_review(
    manifests: list[TrialManifest],
    pre_cfg: KpmsPreprocessConfig,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], list[str]]:
    """Rebuild coordinates/confidences for review (same pipeline as fit/apply)."""
    coordinates, confidences, _bp, skipped = build_kpms_inputs(manifests, pre_cfg)
    return coordinates, confidences, skipped
