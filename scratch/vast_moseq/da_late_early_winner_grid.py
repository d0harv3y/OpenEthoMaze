"""Grid movies for S05 late−early DA winner syllables (one per model).

Crowd movies (keypoint-MoSeq grid) sampled from **S05** experimental trials.
Optional run-phase mask matches bout-kinematics / DA grain.

Regen (OpenEthoMaze repo root; needs ``--extra kpms``)::

    uv run python scratch/vast_moseq/da_late_early_winner_grid.py
    uv run python scratch/vast_moseq/da_late_early_winner_grid.py --model gerstner_vast_fit
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from keypoint_moseq.util import get_syllable_instances, sample_instances
from keypoint_moseq.viz import grid_movie, write_video_clip

_SCRATCH = Path(__file__).resolve().parents[1]
_REPO = _SCRATCH.parent
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from maze.kpms.behavior_ethogram.bout_kinematics import trial_state_for_rows  # noqa: E402
from maze.kpms.frame_alignment import KpmsAlignmentCache, kpms_recording_key  # noqa: E402
from maze.kpms.preprocess import KpmsPreprocessConfig  # noqa: E402
from maze.pipeline.db.trial_key import TrialKey  # noqa: E402
from maze.pipeline.io.file_discovery import TrialManifest, load_manifest_csv  # noqa: E402
from vast_moseq.regen_syllable_bout_kinematics import (  # noqa: E402
    DEFAULT_MANIFEST,
    DEFAULT_PRIMARY,
    DEFAULT_SEED_ROOT,
    DEFAULT_TRACKING,
    KEY_RE,
    _aligned_feedback_states,
    _resolve_trial_group,
    load_primary_exp_keys,
    parse_key,
    resolve_model_results,
)
from vast_moseq.vast_syllable_kruskal import pick_late_early_winners  # noqa: E402

DEFAULT_DA = Path(r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq\_da_trial_windows")
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq\syllable_signatures"
    r"\syllable_prototypes_clustered.csv"
)
DEFAULT_VIDEO_REMAP_FROM = r"E:\videos"
DEFAULT_VIDEO_REMAP_TO = r"C:\Users\admin\Documents\work\sack\datas\videos"
WINNER_CSV = "da_late_early_s05_winners.csv"
N_BODY = 8
BASE_WINDOW_SIZE = 384
DEFAULT_ZOOM = 2.0
ROWS = 4
COLS = 6
SESSION = "S05"


def window_size_for_zoom(zoom: float, *, base: int = BASE_WINDOW_SIZE) -> int:
    """Smaller crop window => tighter zoom on centroid (kpMS ``grid_movie``)."""
    if zoom <= 0:
        raise ValueError(f"zoom must be > 0, got {zoom}")
    raw = int(round(base / zoom))
    block = 16
    return max(block, int(round(raw / block)) * block)


def dummy_coordinates(centroid: np.ndarray) -> np.ndarray:
    """(n, n_body, 2) tiles of centroid so kpMS grid_movie can slice coords."""
    c = np.asarray(centroid, dtype=np.float64)
    if c.ndim != 2 or c.shape[1] != 2:
        raise ValueError(f"centroid shape {c.shape}")
    return np.repeat(c[:, None, :], N_BODY, axis=1)


def remap_video_path(raw: str, remap_from: str, remap_to: str) -> Path:
    p = Path(raw)
    if p.is_file():
        return p
    text = str(p)
    prefix = remap_from.rstrip("\\/")
    if prefix and text.lower().startswith(prefix.lower()):
        suffix = text[len(prefix) :].lstrip("\\/")
        alt = Path(remap_to) / suffix
        if alt.is_file():
            return alt
    return p


def _info_md() -> str:
    return """# INFO — S05 late−early DA winner grid movies

Crowd movies (keypoint-MoSeq grid) of each model's **top positive late−early**
syllable at **S05** (top-right volcano winner).

## Grain

One MP4 per **model**. Cells = sampled bouts on `phase_layer=S05` experimental
trials. Default: **run-phase only** (non-run frames masked before instance find).

`raw_syllable_id` is model-local; filenames include HDBSCAN `cluster_id` when
available from `syllable_prototypes_clustered.csv`.

## Inputs

| Source | Role |
|--------|------|
| `da_late_early_s05_winners.csv` | winner id per model |
| `gerstner_vast_fit/results.h5` / `seed_*/results_apply.h5` | syllable, centroid, heading |
| `gerstner_manifest_local_legacy.csv` | `.avi` video paths |
| `vast_results_legacy.h5` | trial_state for run mask |

Video paths in the manifest use `E:\\videos\\...`; local remap tries
`sack/datas/videos/...` when the E: drive is absent.
"""


def _session_keys(primary_keys: set[str], session: str) -> list[str]:
    out: list[str] = []
    for k in sorted(primary_keys):
        meta = parse_key(k)
        if meta["phase_layer"] == session:
            out.append(k)
    return out


def _manifest_by_key(manifest_path: Path, primary_keys: set[str]) -> dict[str, TrialManifest]:
    out: dict[str, TrialManifest] = {}
    for m in load_manifest_csv(manifest_path):
        if bool(getattr(m, "is_habituation", False)):
            continue
        k = kpms_recording_key(m)
        if k in primary_keys:
            out[k] = m
    return out


def _attach_cluster_id(winners: pd.DataFrame, sig_csv: Path) -> pd.DataFrame:
    if not sig_csv.is_file():
        winners = winners.copy()
        winners["cluster_id"] = -1
        return winners
    sig = pd.read_csv(sig_csv, keep_default_na=False)
    sig = sig[["model", "raw_syllable_id", "cluster_id"]].drop_duplicates()
    sig["raw_syllable_id"] = pd.to_numeric(sig["raw_syllable_id"], errors="coerce")
    out = winners.merge(sig, on=["model", "raw_syllable_id"], how="left")
    out["cluster_id"] = pd.to_numeric(out["cluster_id"], errors="coerce").fillna(-1).astype(int)
    return out


def _mask_run_only(
    syll: np.ndarray,
    manifest: TrialManifest,
    tracking_h5: h5py.File,
    alignment_cache: KpmsAlignmentCache,
    pre_cfg: KpmsPreprocessConfig,
) -> np.ndarray:
    aligned = alignment_cache.aligned_trial(manifest, pre_cfg)
    if aligned is None:
        return syll
    g_trial = _resolve_trial_group(tracking_h5, manifest)
    if g_trial is None:
        return syll
    fb_states = _aligned_feedback_states(g_trial)
    if fb_states is None:
        return syll
    src_idx = np.asarray(aligned.source_frame_indices, dtype=np.int64)
    n = min(len(syll), len(src_idx))
    if n <= 0:
        return syll
    out = np.asarray(syll[:n], dtype=syll.dtype).copy()
    row_states = trial_state_for_rows(fb_states, src_idx[:n])
    for i, st in enumerate(row_states):
        if str(st).strip().lower() != "run":
            out[i] = -1
    if len(syll) > n:
        out = np.concatenate([out, np.full(len(syll) - n, -1, dtype=out.dtype)])
    return out


def _load_trial_bundle(
    *,
    results_h5: Path,
    keys: list[str],
    manifest_by_key: dict[str, TrialManifest],
    tracking_h5: h5py.File | None,
    alignment_cache: KpmsAlignmentCache | None,
    pre_cfg: KpmsPreprocessConfig | None,
    video_remap_from: str,
    video_remap_to: str,
    run_only: bool,
) -> tuple[
    dict[str, dict[str, np.ndarray]],
    dict[str, np.ndarray],
    dict[str, np.ndarray],
    dict[str, str],
]:
    results: dict[str, dict[str, np.ndarray]] = {}
    coords: dict[str, np.ndarray] = {}
    vix: dict[str, np.ndarray] = {}
    video_paths: dict[str, str] = {}
    with h5py.File(results_h5, "r") as f:
        for k in keys:
            manifest = manifest_by_key.get(k)
            if manifest is None or k not in f:
                continue
            raw_vp = str(getattr(manifest, "video_path", "") or "")
            if not raw_vp:
                continue
            vp = remap_video_path(raw_vp, video_remap_from, video_remap_to)
            if not vp.is_file():
                continue
            g = f[k]
            syll = np.asarray(g["syllable"][:])
            cent = np.asarray(g["centroid"][:], dtype=np.float64)
            head = np.asarray(g["heading"][:], dtype=np.float64)
            if run_only and tracking_h5 is not None and alignment_cache is not None and pre_cfg:
                syll = _mask_run_only(syll, manifest, tracking_h5, alignment_cache, pre_cfg)
            if alignment_cache is not None and pre_cfg is not None:
                aligned = alignment_cache.aligned_trial(manifest, pre_cfg)
                if aligned is not None and len(aligned.source_frame_indices) >= len(syll):
                    frame_idx = np.asarray(aligned.source_frame_indices[: len(syll)], dtype=np.int64)
                else:
                    frame_idx = np.arange(len(syll), dtype=np.int64)
            else:
                frame_idx = np.arange(len(syll), dtype=np.int64)
            results[k] = {"syllable": syll, "centroid": cent, "heading": head}
            coords[k] = dummy_coordinates(cent)
            vix[k] = frame_idx
            video_paths[k] = str(vp)
    return results, coords, vix, video_paths


def _render_one(
    *,
    results: dict[str, dict[str, np.ndarray]],
    coordinates: dict[str, np.ndarray],
    video_paths: dict[str, str],
    video_frame_indexes: dict[str, np.ndarray],
    syllable_id: int,
    out_path: Path,
    fps: float,
    window_size: int,
    dot_radius: int,
) -> int:
    syllables = {k: v["syllable"] for k, v in results.items()}
    centroids = {k: v["centroid"] for k, v in results.items()}
    headings = {k: v["heading"] for k, v in results.items()}
    pre = int(round(1.0 * fps))
    post = int(round(2.0 * fps))
    syllable_instances = get_syllable_instances(
        syllables,
        pre=pre,
        post=post,
        min_duration=3,
        min_frequency=0.0,
        min_instances=ROWS * COLS,
    )
    if syllable_id not in syllable_instances:
        return 0
    sampled = sample_instances(
        {syllable_id: syllable_instances[syllable_id]},
        ROWS * COLS,
        coordinates=coordinates,
        centroids=centroids,
        headings=headings,
        n_neighbors=50,
    )
    instances = sampled.get(syllable_id)
    if not instances:
        return 0
    frames = grid_movie(
        instances,
        ROWS,
        COLS,
        video_paths,
        centroids,
        headings,
        window_size,
        video_frame_indexes,
        pre=pre,
        post=post,
        dot_radius=dot_radius,
        overlay_keypoints=False,
        coordinates=coordinates,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_video_clip(frames, str(out_path), fps=fps, quality=7)
    return len(instances)


def _safe_model_token(model: str) -> str:
    return re.sub(r"[^\w.-]+", "_", model)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--sig-csv", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--primary-h5", type=Path, default=DEFAULT_PRIMARY)
    ap.add_argument("--seed-root", type=Path, default=DEFAULT_SEED_ROOT)
    ap.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--tracking-h5", type=Path, default=DEFAULT_TRACKING)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--model", type=str, default=None)
    ap.add_argument("--session", type=str, default=SESSION)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument(
        "--zoom",
        type=float,
        default=DEFAULT_ZOOM,
        help="Centroid crop zoom factor (2 = half window / 2x tighter; default 2)",
    )
    ap.add_argument(
        "--window-size",
        type=int,
        default=None,
        help="Override crop window in px (multiple of 16); default BASE/zoom",
    )
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fdr-only", action="store_true")
    ap.add_argument("--all-trials", action="store_true", help="Disable run-phase mask")
    ap.add_argument("--video-remap-from", type=str, default=DEFAULT_VIDEO_REMAP_FROM)
    ap.add_argument("--video-remap-to", type=str, default=DEFAULT_VIDEO_REMAP_TO)
    args = ap.parse_args(argv)

    np.random.seed(int(args.seed))
    window_size = (
        window_size_for_zoom(1.0, base=int(args.window_size))
        if args.window_size is not None
        else window_size_for_zoom(float(args.zoom))
    )
    dot_radius = max(4, int(round(4 * float(args.zoom) / DEFAULT_ZOOM)))
    out = args.out_dir or (args.da_dir / "grid_movies")
    out.mkdir(parents=True, exist_ok=True)
    (out / "INFO_s05_late_early_winner_grid.md").write_text(_info_md(), encoding="utf-8")

    winner_csv = args.da_dir / WINNER_CSV
    if winner_csv.is_file():
        winners = pd.read_csv(winner_csv, keep_default_na=False)
    else:
        tests = pd.read_csv(args.da_dir / "da_syllable_tests_long.csv", keep_default_na=False)
        winners = pick_late_early_winners(tests, phase_layer=args.session, fdr_only=args.fdr_only)
    if args.fdr_only:
        hit = winners["hit_fdr05"].astype(str).str.lower().isin(("true", "1"))
        winners = winners[hit]
    winners = _attach_cluster_id(winners, args.sig_csv)
    if args.model:
        winners = winners[winners["model"] == args.model]
    if winners.empty:
        print("no winner rows to render", flush=True)
        return 1

    primary_keys = load_primary_exp_keys(args.primary_h5)
    session_keys = _session_keys(primary_keys, args.session)
    manifest_by_key = _manifest_by_key(args.manifest_path, set(session_keys))
    run_only = not args.all_trials
    pre_cfg = KpmsPreprocessConfig() if run_only else None
    alignment_cache = KpmsAlignmentCache() if run_only else None
    tracking_h5_obj: h5py.File | None = None
    if run_only and args.tracking_h5.is_file():
        tracking_h5_obj = h5py.File(args.tracking_h5, "r")

    log: list[dict[str, object]] = []
    t0 = time.perf_counter()
    last_beat = t0
    n = len(winners)
    print(
        f"grid movies: {n} models session={args.session} run_only={run_only} "
        f"window={window_size}px zoom={args.zoom} -> {out}",
        flush=True,
    )

    try:
        for i, row in enumerate(winners.itertuples(index=False), start=1):
            model = str(row.model)
            sid = int(row.raw_syllable_id)
            cid = int(getattr(row, "cluster_id", -1))
            results_h5 = resolve_model_results(
                model, seed_root=args.seed_root, primary_h5=args.primary_h5
            )
            now = time.perf_counter()
            if now - last_beat >= 30.0 or i == 1:
                print(
                    f"[{i}/{n}] {model} syllable {sid} cluster {cid} "
                    f"elapsed={now - t0:.0f}s",
                    flush=True,
                )
                last_beat = now
            if not results_h5.is_file():
                log.append({"model": model, "status": "missing_results_h5"})
                continue
            keys = [k for k in session_keys if k in manifest_by_key]
            results, coords, vix, video_paths = _load_trial_bundle(
                results_h5=results_h5,
                keys=keys,
                manifest_by_key=manifest_by_key,
                tracking_h5=tracking_h5_obj,
                alignment_cache=alignment_cache,
                pre_cfg=pre_cfg,
                video_remap_from=args.video_remap_from,
                video_remap_to=args.video_remap_to,
                run_only=run_only,
            )
            safe = _safe_model_token(model)
            dest = out / f"grid_s05_late_early_{safe}_syll{sid}_cluster{cid}.mp4"
            try:
                n_inst = _render_one(
                    results=results,
                    coordinates=coords,
                    video_paths=video_paths,
                    video_frame_indexes=vix,
                    syllable_id=sid,
                    out_path=dest,
                    fps=float(args.fps),
                    window_size=window_size,
                    dot_radius=dot_radius,
                )
            except Exception as exc:
                log.append(
                    {
                        "model": model,
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "n_sessions": len(results),
                    }
                )
                print(f"  FAIL {model}: {exc}", flush=True)
                continue
            status = "ok" if n_inst and dest.is_file() else "no_instances"
            log.append(
                {
                    "model": model,
                    "status": status,
                    "raw_syllable_id": sid,
                    "cluster_id": cid,
                    "n_trials": len(results),
                    "n_instances": n_inst,
                    "window_size": window_size,
                    "zoom": float(args.zoom),
                    "path": str(dest) if dest.is_file() else "",
                }
            )
            print(f"  {status} instances={n_inst} trials={len(results)} {dest.name}", flush=True)
    finally:
        if tracking_h5_obj is not None:
            tracking_h5_obj.close()

    (out / "run_summary.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    n_ok = sum(1 for r in log if r.get("status") == "ok")
    print(f"done {n_ok}/{n} ok in {time.perf_counter() - t0:.0f}s -> {out}", flush=True)
    return 0 if n_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
