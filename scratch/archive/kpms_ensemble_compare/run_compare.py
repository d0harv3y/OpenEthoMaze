"""One-off kpMS ensemble comparison (scratch). See README.md for methodology."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
import sys

import keypoint_moseq as kpms
import numpy as np

from maze.pipeline.io.file_discovery import load_manifest_csv

_SCRATCH_DIR = Path(__file__).resolve().parent
if str(_SCRATCH_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_DIR))
from movement_layer import aggregate_movement_metrics

DEFAULT_ROOT = Path(r"C:\Users\admin\Documents\work\sack\test")
DEFAULT_LEGACY_DB = DEFAULT_ROOT / "vast_results_legacy.h5"
STREAMS = ("anatomical", "blob", "fused")
SEEDS = ("005", "013", "042", "067", "111")
DELTA = 3
FPS = 30.0

ROOT = DEFAULT_ROOT
LEGACY_DB = DEFAULT_LEGACY_DB
KPMS_MANIFEST = DEFAULT_ROOT / "trial_manifest_kpms_tracking_wsl.csv"
OUT = _SCRATCH_DIR / "output"
EXCLUDED_MODELS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ModelRef:
    stream: str
    seed: str

    @property
    def model_id(self) -> str:
        return f"{self.stream}/seed_{self.seed}"

    @property
    def project_dir(self) -> Path:
        return ROOT / self.stream

    @property
    def model_name(self) -> str:
        return f"seed_{self.seed}"


def discover_models() -> list[ModelRef]:
    models: list[ModelRef] = []
    for stream in STREAMS:
        for seed in SEEDS:
            p = ROOT / stream / f"seed_{seed}" / "results_apply.h5"
            if not p.is_file():
                raise FileNotFoundError(p)
            models.append(ModelRef(stream=stream, seed=seed))
    return models


def load_results(model: ModelRef) -> dict[str, dict]:
    path = model.project_dir / model.model_name / "results_apply.h5"
    return kpms.load_hdf5(str(path))


def syllable_boundaries(syll: np.ndarray) -> np.ndarray:
    """Change-point indices; skip transitions involving -1 (gaps)."""
    s = np.asarray(syll, dtype=np.int64)
    if s.size < 2:
        return np.array([], dtype=np.int64)
    valid = (s[:-1] >= 0) & (s[1:] >= 0)
    changed = s[1:] != s[:-1]
    idx = np.flatnonzero(valid & changed) + 1
    return idx.astype(np.int64, copy=False)


def match_boundaries(b1: np.ndarray, b2: np.ndarray, delta: int) -> tuple[int, int, int]:
    """Greedy one-to-one matching within delta. Returns (matched, |b1|, |b2|)."""
    if b1.size == 0 and b2.size == 0:
        return 0, 0, 0
    if b1.size == 0 or b2.size == 0:
        return 0, int(b1.size), int(b2.size)

    used_b2: set[int] = set()
    matched = 0
    for x in b1:
        best_j = None
        best_d = delta + 1
        for j, y in enumerate(b2):
            if j in used_b2:
                continue
            d = abs(int(x) - int(y))
            if d <= delta and d < best_d:
                best_d = d
                best_j = j
        if best_j is not None:
            used_b2.add(best_j)
            matched += 1
    return matched, int(b1.size), int(b2.size)


def boundary_prf(b1: np.ndarray, b2: np.ndarray, delta: int) -> tuple[float, float, float]:
    m, n1, n2 = match_boundaries(b1, b2, delta)
    if n1 == 0 and n2 == 0:
        return 1.0, 1.0, 1.0
    prec = m / n2 if n2 else 0.0
    rec = m / n1 if n1 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return prec, rec, f1


def run_lengths(syll: np.ndarray) -> list[int]:
    s = np.asarray(syll)
    if s.size == 0:
        return []
    valid = s >= 0
    if not valid.any():
        return []
    runs: list[int] = []
    i = 0
    while i < s.size:
        if s[i] < 0:
            i += 1
            continue
        j = i + 1
        while j < s.size and s[j] == s[i] and s[j] >= 0:
            j += 1
        runs.append(j - i)
        i = j
    return runs


def occupancy_entropy(syll: np.ndarray) -> float:
    s = syll[syll >= 0]
    if s.size == 0:
        return float("nan")
    _, counts = np.unique(s, return_counts=True)
    p = counts / counts.sum()
    return float(-(p * np.log(p + 1e-12)).sum())


def read_selected_trials(model: ModelRef) -> set[str]:
    path = ROOT / model.stream / model.model_name / "selected_trials.csv"
    keys: set[str] = set()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            aid = row.get("animal_id") or row.get("animal") or ""
            sess = row.get("session") or row.get("h5_session") or ""
            trial = row.get("trial") or ""
            keys.add(f"{aid}-{sess}-{trial}")
    return keys


def model_syllable_stats(results: dict[str, dict]) -> dict[str, float | int]:
    all_labels: set[int] = set()
    bout_counts: list[int] = []
    entropies: list[float] = []
    labeled_fracs: list[float] = []
    for rec in results.values():
        syll = np.asarray(rec["syllable"])
        valid = syll >= 0
        labeled_fracs.append(float(valid.mean()) if syll.size else 0.0)
        labs = set(int(x) for x in syll[valid])
        all_labels.update(labs)
        b = syllable_boundaries(syll)
        bout_counts.append(len(b) + (1 if valid.any() else 0))
        entropies.append(occupancy_entropy(syll))
    return {
        "K_used": len(all_labels),
        "n_recordings": len(results),
        "median_bouts_per_trial": float(np.median(bout_counts)) if bout_counts else 0.0,
        "median_entropy": float(np.nanmedian(entropies)) if entropies else float("nan"),
        "median_labeled_frac": float(np.median(labeled_fracs)) if labeled_fracs else 0.0,
    }


def pairwise_boundary_matrix(
    models: list[ModelRef],
    results_by_model: dict[str, dict[str, dict]],
    *,
    delta: int,
    stream_filter: str | None = None,
) -> dict[tuple[str, str], list[float]]:
    """Median boundary F1 per trial for each model pair."""
    if stream_filter:
        models = [m for m in models if m.stream == stream_filter]
    pair_f1s: dict[tuple[str, str], list[float]] = defaultdict(list)

    common_keys = None
    for m in models:
        keys = set(results_by_model[m.model_id].keys())
        common_keys = keys if common_keys is None else common_keys & keys

    assert common_keys is not None
    trial_keys = sorted(common_keys)

    for ma, mb in combinations(models, 2):
        for tk in trial_keys:
            sa = np.asarray(results_by_model[ma.model_id][tk]["syllable"])
            sb = np.asarray(results_by_model[mb.model_id][tk]["syllable"])
            if sa.shape != sb.shape:
                continue
            _, _, f1 = boundary_prf(syllable_boundaries(sa), syllable_boundaries(sb), delta)
            pair_f1s[(ma.model_id, mb.model_id)].append(f1)

    return pair_f1s


def fit_trial_overlap(models: list[ModelRef]) -> dict[str, int]:
    sets = {m.model_id: read_selected_trials(m) for m in models}
    all_trials: set[str] = set()
    for s in sets.values():
        all_trials |= s
    intersection = set.intersection(*sets.values()) if sets else set()
    return {
        "n_fit_trials_per_seed": 80,
        "n_unique_fit_trials_union": len(all_trials),
        "n_intersection_all_15": len(intersection),
    }


def active_models(models: list[ModelRef]) -> list[ModelRef]:
    """Drop checkpoints excluded from ensemble metrics."""
    return [m for m in models if m.model_id not in EXCLUDED_MODELS]


def _resolve_manifest(root: Path, manifest_csv: Path | None) -> Path:
    if manifest_csv is not None:
        return manifest_csv
    for name in (
        "trial_manifest_kpms_tracking_wsl.csv",
        "trial_manifest_kpms_tracking.csv",
    ):
        p = root / name
        if p.is_file():
            return p
    raise FileNotFoundError(f"No kpMS manifest under {root}")


def _resolve_legacy_db(root: Path, legacy_db: Path | None) -> Path:
    if legacy_db is not None:
        return legacy_db
    local = root / "vast_results_legacy.h5"
    if local.is_file():
        return local
    sibling = root.parent / "test" / "vast_results_legacy.h5"
    if sibling.is_file():
        return sibling
    raise FileNotFoundError(
        f"No vast_results_legacy.h5 under {root} or {root.parent / 'test'}"
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="kpMS ensemble root")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: scratch/.../output/<root.name>)",
    )
    p.add_argument("--legacy-db", type=Path, default=None, help="Legacy ambulation H5")
    p.add_argument("--manifest-csv", type=Path, default=None)
    p.add_argument(
        "--exclude-model",
        action="append",
        default=[],
        metavar="STREAM/seed_NNN",
        help="Exclude model from ensemble metrics (repeatable)",
    )
    return p.parse_args()


def main() -> None:
    global ROOT, LEGACY_DB, KPMS_MANIFEST, OUT, EXCLUDED_MODELS

    args = parse_args()
    ROOT = args.root
    OUT = args.out or (_SCRATCH_DIR / "output" / ROOT.name)
    KPMS_MANIFEST = _resolve_manifest(ROOT, args.manifest_csv)
    LEGACY_DB = _resolve_legacy_db(ROOT, args.legacy_db)
    if args.exclude_model:
        EXCLUDED_MODELS = frozenset(args.exclude_model)
    else:
        EXCLUDED_MODELS = frozenset()

    OUT.mkdir(parents=True, exist_ok=True)
    models = discover_models()
    ensemble_models = active_models(models)
    print(f"Found {len(models)} models under {ROOT} ({len(ensemble_models)} ensemble-active)")

    results_by_model: dict[str, dict[str, dict]] = {}
    syllable_summary_rows: list[dict] = []

    for m in models:
        print(f"Loading {m.model_id} ...")
        res = load_results(m)
        results_by_model[m.model_id] = res
        stats = model_syllable_stats(res)
        syllable_summary_rows.append({"model_id": m.model_id, **stats})

    # Syllable count summary
    sc_path = OUT / "syllable_count_summary.csv"
    with sc_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(syllable_summary_rows[0].keys()))
        w.writeheader()
        w.writerows(syllable_summary_rows)
    print(f"Wrote {sc_path}")

    # Fit trial overlap (per stream + global)
    overlap_rows: list[dict] = []
    for stream in STREAMS:
        sm = [m for m in models if m.stream == stream]
        sets = [read_selected_trials(m) for m in sm]
        union = set().union(*sets)
        inter = set.intersection(*sets)
        pair_jaccards = []
        for a, b in combinations(sets, 2):
            pair_jaccards.append(len(a & b) / len(a | b) if (a | b) else 1.0)
        overlap_rows.append(
            {
                "stream": stream,
                "union_fit_trials": len(union),
                "intersection_5_seeds": len(inter),
                "median_pairwise_jaccard": float(np.median(pair_jaccards)),
            }
        )
    overlap_rows.append({"stream": "all_15", **fit_trial_overlap(models)})

    # Boundary agreement within each stream
    boundary_rows: list[dict] = []
    for stream in STREAMS:
        pair_f1s = pairwise_boundary_matrix(
            ensemble_models, results_by_model, delta=DELTA, stream_filter=stream
        )
        for (a, b), f1s in sorted(pair_f1s.items()):
            boundary_rows.append(
                {
                    "stream": stream,
                    "model_a": a,
                    "model_b": b,
                    "delta_frames": DELTA,
                    "n_trials": len(f1s),
                    "median_boundary_f1": float(np.median(f1s)),
                    "mean_boundary_f1": float(np.mean(f1s)),
                    "p25_boundary_f1": float(np.percentile(f1s, 25)),
                    "p75_boundary_f1": float(np.percentile(f1s, 75)),
                }
            )

    ba_path = OUT / "boundary_agreement.csv"
    with ba_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(boundary_rows[0].keys()))
        w.writeheader()
        w.writerows(boundary_rows)
    print(f"Wrote {ba_path}")

    # Stream-level median F1 heatmap data (5x5 per stream)
    for stream in STREAMS:
        mat = np.full((5, 5), np.nan)
        seed_idx = {s: i for i, s in enumerate(SEEDS)}
        stream_pairs = [r for r in boundary_rows if r["stream"] == stream]
        for r in stream_pairs:
            sa = r["model_a"].split("/")[-1].replace("seed_", "")
            sb = r["model_b"].split("/")[-1].replace("seed_", "")
            i, j = seed_idx[sa], seed_idx[sb]
            mat[i, j] = r["median_boundary_f1"]
            mat[j, i] = r["median_boundary_f1"]
        np.fill_diagonal(mat, 1.0)
        np.savetxt(
            OUT / f"boundary_f1_matrix_{stream}.csv",
            mat,
            delimiter=",",
            header=",".join(SEEDS),
            comments="",
        )

    # Sample trial: strict Jaccard + bout stats for anatomical seeds
    sample_trial = "3243-S01-T01"
    trial_rows: list[dict] = []
    for m in [x for x in models if x.stream == "anatomical"]:
        syll = np.asarray(results_by_model[m.model_id][sample_trial]["syllable"])
        b = syllable_boundaries(syll)
        runs = run_lengths(syll)
        trial_rows.append(
            {
                "trial": sample_trial,
                "model_id": m.model_id,
                "T": len(syll),
                "K_trial": len(set(int(x) for x in syll if x >= 0)),
                "n_boundaries": len(b),
                "median_bout_frames": float(np.median(runs)) if runs else 0.0,
            }
        )

    # Movement correlation (legacy ambulation join)
    print("\nMovement layer: joining vast_results_legacy.h5 ambulation ...")
    manifest_by_key = {m.kpms_results_dict_key: m for m in load_manifest_csv(KPMS_MANIFEST)}
    mov_summary, mov_trial = aggregate_movement_metrics(
        ensemble_models,
        results_by_model,
        manifest_by_key,
        LEGACY_DB,
        delta=DELTA,
        exclude_models=EXCLUDED_MODELS,
        tracking_db=ROOT / "kpms_tracking.h5",
    )
    mov_path = OUT / "movement_correlation.csv"
    with mov_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mov_summary[0].keys()))
        w.writeheader()
        w.writerows(mov_summary)
    print(f"Wrote {mov_path}")

    mov_trial_path = OUT / "trial_movement_correlation.csv"
    with mov_trial_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mov_trial[0].keys()))
        w.writeheader()
        w.writerows(mov_trial)
    print(f"Wrote {mov_trial_path} ({len(mov_trial)} rows)")

    report = {
        "root": str(ROOT),
        "n_models": len(models),
        "n_ensemble_models": len(ensemble_models),
        "excluded_models": sorted(EXCLUDED_MODELS),
        "legacy_ambulation_db": str(LEGACY_DB),
        "movement_correlation_summary": mov_summary,
        "delta_frames": DELTA,
        "delta_ms_approx": DELTA / FPS * 1000,
        "syllable_count_summary": syllable_summary_rows,
        "fit_trial_overlap": overlap_rows,
        "boundary_agreement_by_stream": {
            stream: {
                "median_of_pair_medians": float(
                    np.median([r["median_boundary_f1"] for r in boundary_rows if r["stream"] == stream])
                ),
                "min_pair_median": float(
                    min(r["median_boundary_f1"] for r in boundary_rows if r["stream"] == stream)
                ),
                "max_pair_median": float(
                    max(r["median_boundary_f1"] for r in boundary_rows if r["stream"] == stream)
                ),
            }
            for stream in STREAMS
        },
        "sample_trial_anatomical": trial_rows,
        "notes": [
            "Raw syllable IDs are NOT comparable across models; boundary F1 is segmentation agreement.",
            "Cross-stream boundary F1 omitted (different pose geometry / preprocess keep masks).",
            "Movement layer uses legacy ambulation_metrics/spot (fallback centroid) joined by source frame_index.",
            (
                f"Excluded models: {sorted(EXCLUDED_MODELS)}."
                if EXCLUDED_MODELS
                else "No models excluded (use --exclude-model to omit specific fits)."
            ),
        ],
    }
    report_path = OUT / "ensemble_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {report_path}")

    # Console summary
    print("\n=== Syllable K (used labels) per model ===")
    for row in syllable_summary_rows:
        print(f"  {row['model_id']:22s} K={row['K_used']:3d}  recordings={row['n_recordings']}")

    print(f"\n=== Boundary F1 @ delta={DELTA} frames (median over trials, per stream) ===")
    for stream in STREAMS:
        vals = [r["median_boundary_f1"] for r in boundary_rows if r["stream"] == stream]
        print(
            f"  {stream:12s}  pair medians: min={min(vals):.3f}  median={np.median(vals):.3f}  max={max(vals):.3f}"
        )

    print("\n=== Movement vs syllable boundaries (median F1 per model) ===")
    for row in mov_summary:
        print(
            f"  {row['model_id']:22s}  moving_f1={row['median_boundary_vs_moving_f1']:.3f}"
            f"  dspeed_ratio={row['median_boundary_dspeed_ratio']:.2f}"
        )

    print("\n=== Fit-trial overlap (80 trials/seed) ===")
    for row in overlap_rows:
        print(f"  {row}")


if __name__ == "__main__":
    main()
