"""Grid movies for the TX pooled DA argmax syllable (cluster_id 13).

One 4x6 crowd movie per paramscan model, sampled from NOR_TX / novel_obj
sessions. raw_syllable_id is model-local; labels include cluster_id.

Regen (OpenEthoMaze repo root; needs --extra kpms)::

    uv run python scratch/nor_object_mi/tx_argmax_grid.py
    uv run python scratch/nor_object_mi/tx_argmax_grid.py --model paramscan_s1-1e8_s2-1e5_ss-50
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from keypoint_moseq.util import get_syllable_instances, sample_instances
from keypoint_moseq.viz import grid_movie, write_video_clip

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402

DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_ENSEMBLE = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
DEFAULT_NOR = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\my_NOR_results.h5")
DEFAULT_VIDEO_ROOT = Path(r"C:\Users\admin\Documents\work\sack\datas\impress")
KPMS_PREFIX = "D:-nor vids-"
WINNER_CSV = "tx_pooled_argmax_syllable.csv"
NOVELTY_STEP = "identical->novel"
PHASE = "NOR_TX"
CONDITION = "novel_obj"
N_BODY = 8
WINDOW_SIZE = 384
ROWS = 4
COLS = 6


def kpms_key_to_mp4(kpms_key: str, video_root: Path) -> Path:
    """Map native kpMS group name to the NOR mp4 under impress/."""
    if not kpms_key.startswith(KPMS_PREFIX):
        raise ValueError(f"unexpected kpMS key prefix: {kpms_key[:80]!r}")
    rest = kpms_key[len(KPMS_PREFIX) :]
    parts = rest.split("-", 3)
    if len(parts) != 4:
        raise ValueError(f"cannot split kpMS key: {kpms_key[:120]!r}")
    rel, exp, animal, fname = parts
    stem = fname[:-3] if fname.lower().endswith(".h5") else Path(fname).stem
    return Path(video_root) / rel / exp / animal / f"{stem}.mp4"


def dummy_coordinates(centroid: np.ndarray) -> np.ndarray:
    """(n, n_body, 2) tiles of centroid so kpMS grid_movie can slice coords."""
    c = np.asarray(centroid, dtype=np.float64)
    if c.ndim != 2 or c.shape[1] != 2:
        raise ValueError(f"centroid shape {c.shape}")
    return np.repeat(c[:, None, :], N_BODY, axis=1)


def _info_md() -> str:
    return """# INFO — TX argmax syllable grid movies

Crowd movies (keypoint-MoSeq grid) of the **NOR_TX** pooled DA winner
(argmax median Δp; **cluster_id = 13** in `syllable_prototypes_clustered.csv`).

## Grain

One MP4 per **model**. Cells = sampled bouts of that model's `raw_syllable_id`
on `phase_layer=NOR_TX` and `condition_layer=novel_obj`.

`raw_syllable_id` is **not** portable across models. The shared claim is
HDBSCAN `cluster_id=13` (pause/still-like kinematics).

## Inputs

| Source | Role |
|--------|------|
| `tx_pooled_argmax_syllable.csv` | winner id (novelty step `identical->novel`) |
| `paramscan_*/results.h5` | syllable, centroid, heading |
| `my_NOR_results.h5` | join + cohort filter |
| `impress/standard format/**/*.mp4` | video tiles |

kpMS row index = video frame index on checked NOR files (1:1).

## Not

Not a shared syllable label. Not occupancy DA itself. Not keypoints-only.
"""


def _winners_novelty(da_dir: Path) -> pd.DataFrame:
    w = pd.read_csv(da_dir / WINNER_CSV)
    sub = w[(w["phase_layer"] == PHASE) & (w["step"] == NOVELTY_STEP)].copy()
    if sub.empty:
        raise SystemExit(f"no novelty TX winners in {da_dir / WINNER_CSV}")
    return sub.sort_values("model")


def _load_slim(
    results_h5: Path, keys: list[str]
) -> tuple[dict[str, dict[str, np.ndarray]], dict[str, np.ndarray], dict[str, np.ndarray]]:
    results: dict[str, dict[str, np.ndarray]] = {}
    coords: dict[str, np.ndarray] = {}
    with h5py.File(results_h5, "r") as f:
        for k in keys:
            if k not in f:
                continue
            g = f[k]
            syll = np.asarray(g["syllable"][:])
            cent = np.asarray(g["centroid"][:], dtype=np.float64)
            head = np.asarray(g["heading"][:], dtype=np.float64)
            results[k] = {"syllable": syll, "centroid": cent, "heading": head}
            coords[k] = dummy_coordinates(cent)
    return results, coords, {k: np.arange(len(results[k]["syllable"])) for k in results}


def _render_one(
    *,
    results: dict[str, dict[str, np.ndarray]],
    coordinates: dict[str, np.ndarray],
    video_paths: dict[str, str],
    video_frame_indexes: dict[str, np.ndarray],
    syllable_id: int,
    out_path: Path,
    fps: float,
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
        WINDOW_SIZE,
        video_frame_indexes,
        pre=pre,
        post=post,
        overlay_keypoints=False,
        coordinates=coordinates,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_video_clip(frames, str(out_path), fps=fps, quality=7)
    return len(instances)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--ensemble-root", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR)
    ap.add_argument("--video-root", type=Path, default=DEFAULT_VIDEO_ROOT)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--model", type=str, default=None)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    np.random.seed(int(args.seed))
    out = args.out_dir or (args.da_dir / "grid_movies")
    out.mkdir(parents=True, exist_ok=True)
    (out / "INFO_tx_argmax_grid.md").write_text(_info_md(), encoding="utf-8")

    winners = _winners_novelty(args.da_dir)
    if args.model:
        winners = winners[winners["model"] == args.model]
        if winners.empty:
            print(f"no winner row for {args.model}", flush=True)
            return 1

    log: list[dict[str, object]] = []
    t0 = time.perf_counter()
    last_beat = t0
    n = len(winners)
    print(f"grid movies: {n} models -> {out}", flush=True)

    with h5py.File(args.nor_h5, "r") as nor_h5:
        kept = set(filter_cohort(nor_h5)["kept_ids"])  # type: ignore[arg-type]
        for i, row in enumerate(winners.itertuples(index=False), start=1):
            model = str(row.model)
            sid = int(row.raw_syllable_id)
            cid = int(row.cluster_id) if hasattr(row, "cluster_id") else 13
            results_h5 = args.ensemble_root / model / "results.h5"
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
            with h5py.File(results_h5, "r") as kpms_h5:
                sessions = [
                    s
                    for s in iter_joined_sessions(
                        nor_h5, kpms_h5, kept_ids=kept, phase_layer=PHASE
                    )
                    if s.condition_layer == CONDITION
                ]
            keys = [s.kpms_key for s in sessions]
            video_paths: dict[str, str] = {}
            keep_keys: list[str] = []
            n_miss_vid = 0
            for k in keys:
                mp4 = kpms_key_to_mp4(k, args.video_root)
                if mp4.is_file():
                    video_paths[k] = str(mp4)
                    keep_keys.append(k)
                else:
                    n_miss_vid += 1
            results, coords, vix = _load_slim(results_h5, keep_keys)
            # drop keys without video
            results = {k: results[k] for k in keep_keys if k in results}
            coords = {k: coords[k] for k in results}
            vix = {k: vix[k] for k in results}
            video_paths = {k: video_paths[k] for k in results}
            safe = model.replace("paramscan_", "")
            dest = out / f"grid_tx_argmax_{safe}_syll{sid}_cluster{cid}.mp4"
            try:
                n_inst = _render_one(
                    results=results,
                    coordinates=coords,
                    video_paths=video_paths,
                    video_frame_indexes=vix,
                    syllable_id=sid,
                    out_path=dest,
                    fps=float(args.fps),
                )
            except Exception as exc:
                log.append(
                    {
                        "model": model,
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "n_sessions": len(keep_keys),
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
                    "n_sessions": len(keep_keys),
                    "n_missing_video": n_miss_vid,
                    "n_instances": n_inst,
                    "path": str(dest) if dest.is_file() else "",
                }
            )
            print(f"  {status} instances={n_inst} {dest.name}", flush=True)

    (out / "run_summary.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    n_ok = sum(1 for r in log if r.get("status") == "ok")
    print(f"done {n_ok}/{n} ok in {time.perf_counter() - t0:.0f}s -> {out}", flush=True)
    return 0 if n_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
