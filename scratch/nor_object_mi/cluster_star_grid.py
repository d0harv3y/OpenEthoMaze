"""Grid movies for HDBSCAN clusters with >1 majority * on mean-model Kruskal overviews.

Default: one 4×6 crowd movie per multi-star cluster, using the model with the
most bouts for that cluster's representative syllable (max ``n_bouts`` within
model × cluster). Same NOR_TX / nvl_obj sampling as ``tx_argmax_grid``.

Regen (repo root; needs ``--extra kpms``)::

    uv run python scratch/nor_object_mi/cluster_star_grid.py
    uv run python scratch/nor_object_mi/cluster_star_grid.py --all-models
    uv run python scratch/nor_object_mi/cluster_star_grid.py --clusters 30,47
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

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.cluster_tx_kruskal import representative_cluster_ids  # noqa: E402
from nor_object_mi.join_keys import filter_cohort, iter_joined_sessions  # noqa: E402
from nor_object_mi.tx_argmax_grid import (  # noqa: E402
    CONDITION,
    DEFAULT_ENSEMBLE,
    DEFAULT_NOR,
    DEFAULT_VIDEO_ROOT,
    PHASE,
    _load_slim,
    _render_one,
    kpms_key_to_mp4,
)

DEFAULT_MI = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017\_nor_object_mi"
)
DEFAULT_DA = DEFAULT_MI / "simpler_first_da"
DEFAULT_PP = DEFAULT_MI / "simpler_first_phase_paired"
DEFAULT_SIG = DEFAULT_MI / "simpler_first_syllable_signatures"


def clusters_with_min_stars(
    da_csv: Path,
    pp_csv: Path,
    *,
    min_stars: int = 2,
    source: str = "union",
) -> pd.DataFrame:
    """Count majority ``hit_fdr05`` cells per cluster; keep those with ≥ min_stars.

    ``source``: ``union`` (DA+PP), ``da``, or ``pp``.
    """
    frames: list[pd.DataFrame] = []
    if source in ("union", "da") and da_csv.is_file():
        da = pd.read_csv(da_csv)
        frames.append(da.loc[da["hit_fdr05"].astype(bool), ["cluster_id"]].assign(design="da"))
    if source in ("union", "pp") and pp_csv.is_file():
        pp = pd.read_csv(pp_csv)
        frames.append(pp.loc[pp["hit_fdr05"].astype(bool), ["cluster_id"]].assign(design="pp"))
    if not frames:
        return pd.DataFrame(columns=["cluster_id", "n_stars", "n_da", "n_pp"])
    u = pd.concat(frames, ignore_index=True)
    g = (
        u.groupby("cluster_id", sort=True)
        .agg(
            n_stars=("cluster_id", "size"),
            n_da=("design", lambda s: int((s == "da").sum())),
            n_pp=("design", lambda s: int((s == "pp").sum())),
        )
        .reset_index()
    )
    return g[g["n_stars"] >= int(min_stars)].sort_values(
        ["n_stars", "cluster_id"], ascending=[False, True]
    )


def pick_jobs(
    proto: pd.DataFrame,
    cluster_ids: list[int],
    *,
    all_models: bool,
) -> pd.DataFrame:
    """One row per (model, cluster) to render; default = max-n_bouts model per cluster."""
    reps = representative_cluster_ids(proto, include_noise=True)
    reps = reps[reps["cluster_id"].isin(cluster_ids)].copy()
    if reps.empty:
        return reps
    if all_models:
        return reps.sort_values(["cluster_id", "model"]).reset_index(drop=True)
    idx = reps.groupby("cluster_id", sort=True)["n_bouts"].idxmax()
    return reps.loc[idx].sort_values("cluster_id").reset_index(drop=True)


def _info_md(clusters: pd.DataFrame, *, all_models: bool, source: str, min_stars: int) -> str:
    rows = "\n".join(
        f"| {int(r.cluster_id)} | {int(r.n_stars)} | {int(r.n_da)} | {int(r.n_pp)} |"
        for r in clusters.itertuples(index=False)
    )
    mode = "all models with a mapped syllable" if all_models else "one model per cluster (max n_bouts)"
    return f"""# INFO — Multi-star cluster grid movies

Crowd movies (keypoint-MoSeq grid) for HDBSCAN clusters with ≥{min_stars}
majority `*` on mean-model Kruskal overviews (`source={source}`).

## Mode

{mode}

## Grain

Cells = sampled bouts of that model's representative `raw_syllable_id`
(max `n_bouts` within model × cluster) on `session=NOR_TX` /
`trial=nvl_obj`.

`raw_syllable_id` is **not** portable. Shared claim = HDBSCAN `cluster_id`.

## Selected clusters

| cluster_id | n_stars | n_da | n_pp |
|------------|--------:|-----:|-----:|
{rows}

## Not

Not the Kruskal claim itself. Not occupancy DA. Not keypoints-only.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--pp-dir", type=Path, default=DEFAULT_PP)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--ensemble-root", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR)
    ap.add_argument("--video-root", type=Path, default=DEFAULT_VIDEO_ROOT)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--min-stars", type=int, default=2)
    ap.add_argument(
        "--source",
        choices=("union", "da", "pp"),
        default="union",
        help="Which mean-model overview(s) count * toward min-stars",
    )
    ap.add_argument(
        "--clusters",
        type=str,
        default=None,
        help="Comma-separated cluster_ids (skip auto select from * counts)",
    )
    ap.add_argument(
        "--all-models",
        action="store_true",
        help="One MP4 per model×cluster (default: one model per cluster)",
    )
    ap.add_argument("--model", type=str, default=None, help="Restrict to one paramscan model")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    np.random.seed(int(args.seed))
    da_csv = args.da_dir / "cluster_tx_kruskal_mean_model_p.csv"
    pp_csv = args.pp_dir / "phase_paired_cluster_tx_kruskal_mean_model_p.csv"
    proto = pd.read_csv(args.sig_dir / "syllable_prototypes_clustered.csv")

    if args.clusters:
        cids = [int(x.strip()) for x in args.clusters.split(",") if x.strip()]
        stars = pd.DataFrame(
            {"cluster_id": cids, "n_stars": np.nan, "n_da": np.nan, "n_pp": np.nan}
        )
    else:
        stars = clusters_with_min_stars(
            da_csv, pp_csv, min_stars=int(args.min_stars), source=str(args.source)
        )
        cids = [int(x) for x in stars["cluster_id"].tolist()]
        if not cids:
            print(f"no clusters with ≥{args.min_stars} * (source={args.source})", flush=True)
            return 1

    jobs = pick_jobs(proto, cids, all_models=bool(args.all_models))
    if args.model:
        jobs = jobs[jobs["model"] == args.model]
    if jobs.empty:
        print("no representative syllables for selected clusters", flush=True)
        return 1

    out = args.out_dir or (DEFAULT_MI / "cluster_star_grid_movies")
    out.mkdir(parents=True, exist_ok=True)
    (out / "INFO_cluster_star_grid.md").write_text(
        _info_md(stars if not stars.empty else pd.DataFrame({"cluster_id": cids}),
                 all_models=bool(args.all_models),
                 source=str(args.source),
                 min_stars=int(args.min_stars)),
        encoding="utf-8",
    )
    stars.to_csv(out / "selected_clusters.csv", index=False)
    jobs.to_csv(out / "render_jobs.csv", index=False)

    log: list[dict[str, object]] = []
    t0 = time.perf_counter()
    last_beat = t0
    n = len(jobs)
    print(
        f"cluster star grids: {n} jobs, clusters={cids}, "
        f"all_models={args.all_models} -> {out}",
        flush=True,
    )

    with h5py.File(args.nor_h5, "r") as nor_h5:
        kept = set(filter_cohort(nor_h5)["kept_ids"])  # type: ignore[arg-type]
        for i, row in enumerate(jobs.itertuples(index=False), start=1):
            model = str(row.model)
            sid = int(row.raw_syllable_id)
            cid = int(row.cluster_id)
            results_h5 = args.ensemble_root / model / "results.h5"
            now = time.perf_counter()
            if now - last_beat >= 30.0 or i == 1:
                print(
                    f"[{i}/{n}] {model} syll={sid} cluster={cid} "
                    f"elapsed={now - t0:.0f}s",
                    flush=True,
                )
                last_beat = now
            if not results_h5.is_file():
                log.append({"model": model, "cluster_id": cid, "status": "missing_results_h5"})
                continue
            with h5py.File(results_h5, "r") as kpms_h5:
                sessions = [
                    s
                    for s in iter_joined_sessions(
                        nor_h5, kpms_h5, kept_ids=kept, session=PHASE
                    )
                    if s.trial == CONDITION
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
            results = {k: results[k] for k in keep_keys if k in results}
            coords = {k: coords[k] for k in results}
            vix = {k: vix[k] for k in results}
            video_paths = {k: video_paths[k] for k in results}
            safe = model.replace("paramscan_", "")
            dest = out / f"grid_cluster{cid}_{safe}_syll{sid}.mp4"
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
                        "cluster_id": cid,
                        "raw_syllable_id": sid,
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "n_sessions": len(keep_keys),
                    }
                )
                print(f"  FAIL cluster {cid} {model}: {exc}", flush=True)
                continue
            status = "ok" if n_inst and dest.is_file() else "no_instances"
            log.append(
                {
                    "model": model,
                    "cluster_id": cid,
                    "raw_syllable_id": sid,
                    "n_bouts": int(row.n_bouts),
                    "status": status,
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
