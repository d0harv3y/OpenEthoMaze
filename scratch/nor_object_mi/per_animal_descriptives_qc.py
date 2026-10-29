"""Per-animal syllable duration inventory + accent QC heatmaps.

Grain-agnostic (no alphabet equating). Builds syllable bout inventory from each
``results.h5``, then 18 median-bout-duration heatmaps:

  sex × condition × num_states  (2 × 3 × 3 = 18)

Each panel: y = animal-local models at that ``ss`` (sorted animal × κ₂),
x = within-model frequency rank (0 = most used), color = median bout frames.

Regen (OpenEthoMaze repo root):

  uv run python scratch/nor_object_mi/per_animal_descriptives_qc.py
  uv run python scratch/nor_object_mi/per_animal_descriptives_qc.py --figures-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.bout_kinematics import (  # noqa: E402
    discover_per_animal_paramscan_models,
)
from nor_object_mi.join_keys import filter_cohort  # noqa: E402
from nor_object_mi.ngram_decisions import DEFAULT_MIN_BOUT_FRAMES_CLEAN  # noqa: E402
from nor_object_mi.syllable_cleanup import maybe_absorb_short_bouts  # noqa: E402

DEFAULT_NOR = Path(r"D:\sack\datas\impress\my_NOR_results.h5")
DEFAULT_ENSEMBLE = Path(
    r"D:\sack\datas\impress\nor_per_animal_paramscan"
)

_MODEL_RE = re.compile(
    r"^(?P<animal>\d+)_paramscan_s1-(?P<k1>[^_]+)_s2-(?P<k2>[^_]+)_ss-(?P<ss>\d+)"
    r"(?:_ct-(?P<ct>[0-9.eE+-]+))?$"
)

SEXES = ("F", "M")
CONDITIONS = ("noSD", "GHSD", "RBSD")
NUM_STATES = (50, 75, 100)
MIN_BOUT = DEFAULT_MIN_BOUT_FRAMES_CLEAN

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    }
)


def parse_model(name: str) -> dict[str, object]:
    m = _MODEL_RE.match(name)
    if m is None:
        raise ValueError(f"unrecognized per-animal model name: {name!r}")
    k2 = m.group("k2")
    # Folder tokens are already 1e4 / 3e4 / 1e5; keep them. Numeric
    # fallback covers pooled-fit names like 31622.776…
    try:
        k2_f = float(k2)
    except ValueError:
        k2_f = float("nan")
    if k2 in {"1e4", "3e4", "1e5"}:
        k2_label = k2
    elif abs(k2_f - 31622.776601683792) < 1.0 or (
        np.isfinite(k2_f) and 2.0e4 <= k2_f < 5.0e4
    ):
        k2_label = "3e4"
    elif np.isfinite(k2_f) and k2_f >= 5.0e4:
        k2_label = "1e5"
    elif np.isfinite(k2_f) and k2_f >= 5.0e3:
        k2_label = "1e4"
    else:
        k2_label = k2
    return {
        "model": name,
        "animal_id": m.group("animal"),
        "kappa1": m.group("k1"),
        "kappa2": k2,
        "kappa2_f": k2_f,
        "kappa2_label": k2_label,
        "ss": int(m.group("ss")),
        "conf_threshold": m.group("ct") or "",
        "row_label": f"{m.group('animal')} κ₂={k2_label}",
    }


def rle(z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if z.size == 0:
        empty = np.empty(0, np.int64)
        return empty, empty
    ch = np.flatnonzero(z[1:] != z[:-1]) + 1
    starts = np.concatenate(([0], ch))
    ends = np.concatenate((ch, [z.size]))
    return z[starts].astype(np.int64), (ends - starts).astype(np.int64)


def summarize_model(path: Path, *, cleanup: bool) -> tuple[dict, list[dict]]:
    syll_bout_counts: dict[int, int] = {}
    syll_frame_counts: dict[int, int] = {}
    syll_durs: dict[int, list[int]] = {}
    all_durs: list[np.ndarray] = []
    n_rec = 0
    n_frames_tot = 0
    with h5py.File(path, "r") as f:
        for key in f.keys():
            z = np.asarray(f[key]["syllable"], dtype=np.int64)
            if cleanup:
                z = maybe_absorb_short_bouts(z, MIN_BOUT)
            n_rec += 1
            n_frames_tot += int(z.size)
            labels, durs = rle(z)
            all_durs.append(durs)
            for lab, dur in zip(labels.tolist(), durs.tolist()):
                syll_bout_counts[lab] = syll_bout_counts.get(lab, 0) + 1
                syll_frame_counts[lab] = syll_frame_counts.get(lab, 0) + int(dur)
                syll_durs.setdefault(lab, []).append(int(dur))
    d = np.concatenate(all_durs) if all_durs else np.empty(0, np.int64)
    used = sorted(syll_bout_counts)
    ranked = sorted(used, key=lambda s: (-syll_bout_counts[s], s))
    rank_of = {s: r for r, s in enumerate(ranked)}
    count_rows: list[dict] = []
    for s in used:
        count_rows.append(
            {
                "raw_syllable_id": int(s),
                "freq_rank": int(rank_of[s]),
                "n_bouts": int(syll_bout_counts[s]),
                "n_frames": int(syll_frame_counts[s]),
                "occupancy": (
                    syll_frame_counts[s] / n_frames_tot if n_frames_tot else 0.0
                ),
                "median_bout_frames": float(np.median(syll_durs[s])),
                "mean_bout_frames": float(np.mean(syll_durs[s])),
            }
        )
    model_row = {
        "n_recordings": n_rec,
        "n_frames": n_frames_tot,
        "n_syllables_used": len(used),
        "n_bouts": int(d.size),
        "median_bout_frames": float(np.median(d)) if d.size else np.nan,
        "mean_bout_frames": float(np.mean(d)) if d.size else np.nan,
        "frac_lt_min": float(np.mean(d < MIN_BOUT)) if d.size else np.nan,
    }
    return model_row, count_rows


def animal_labels(nor_h5: h5py.File, kept: set[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for aid in kept:
        node = nor_h5[aid]
        cond = str(node.attrs.get("condition", "") or node.attrs.get("tx", "") or "")
        sex = str(node.attrs.get("sex", "") or "")
        cohort = str(node.attrs.get("cohort", "") or "")
        out[aid] = {"sex": sex, "condition": cond, "cohort": cohort}
    return out


def extract_inventory(ensemble_root: Path, nor_h5_path: Path, out: Path) -> None:
    models = discover_per_animal_paramscan_models(ensemble_root)
    if not models:
        raise SystemExit("No per-animal results.h5 found")

    with h5py.File(nor_h5_path, "r") as nor_h5:
        cohort = filter_cohort(nor_h5)
        kept = set(cohort["kept_ids"])  # type: ignore[arg-type]
        labels = animal_labels(nor_h5, kept)
        (out / "cohort_filter.json").write_text(json.dumps(cohort, indent=2), encoding="utf-8")

    model_rows: list[dict] = []
    count_rows: list[dict] = []
    n = len(models)
    t0 = time.perf_counter()
    for i, (name, path) in enumerate(models, start=1):
        meta = parse_model(name)
        aid = str(meta["animal_id"])
        lab = labels.get(aid, {"sex": "", "condition": "", "cohort": ""})
        if aid not in kept:
            print(f"[{i}/{n}] SKIP not in cohort {name}", flush=True)
            continue
        print(f"[{i}/{n}] {name}", flush=True)
        mrow, crows = summarize_model(path, cleanup=True)
        model_rows.append({**meta, **lab, **mrow, "results_h5": str(path)})
        for cr in crows:
            count_rows.append({**meta, **lab, **cr})
        if i % 50 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  … {i}/{n} in {elapsed / 60:.1f} min", flush=True)

    model_df = pd.DataFrame(model_rows).sort_values(
        ["ss", "condition", "sex", "animal_id", "kappa2_f"]
    )
    count_df = pd.DataFrame(count_rows)
    # Keep kappa tokens as strings (pandas otherwise parses "3e4" → 30000.0).
    for col in ("kappa1", "kappa2", "kappa2_label"):
        if col in model_df.columns:
            model_df[col] = model_df[col].astype(str)
        if col in count_df.columns:
            count_df[col] = count_df[col].astype(str)
    model_df.to_csv(out / "model_summary_clean.csv", index=False)
    count_df.to_csv(out / "syllable_counts_clean.csv", index=False)
    sex_cond = {}
    if len(model_df):
        sex_cond = {
            f"{a}|{b}": int(v)
            for (a, b), v in model_df.groupby(["sex", "condition"]).size().items()
        }
    summary = {
        "n_models": int(len(model_df)),
        "n_syllable_rows": int(len(count_df)),
        "min_bout_frames_absorb": MIN_BOUT,
        "sex_condition_counts": sex_cond,
        "elapsed_s": time.perf_counter() - t0,
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        f"Wrote model_summary_clean.csv ({len(model_df)}) + "
        f"syllable_counts_clean.csv ({len(count_df)})",
        flush=True,
    )


def shared_vmax(count_df: pd.DataFrame) -> float:
    v = float(np.nanpercentile(count_df["median_bout_frames"].to_numpy(dtype=float), 95))
    return max(20.0, float(round(v)))


def fig_median_duration_panel(
    model_df: pd.DataFrame,
    count_df: pd.DataFrame,
    *,
    sex: str,
    condition: str,
    ss: int,
    vmax: float,
    fig_dir: Path,
) -> Path | None:
    sub_m = model_df[
        (model_df["sex"] == sex)
        & (model_df["condition"] == condition)
        & (model_df["ss"] == ss)
    ].copy()
    if sub_m.empty:
        print(f"  empty panel sex={sex} condition={condition} ss={ss}", flush=True)
        return None
    sub_m = sub_m.sort_values(["animal_id", "kappa2_f"]).reset_index(drop=True)
    order = sub_m["model"].tolist()
    label_map = dict(zip(sub_m["model"], sub_m["row_label"]))
    sub_c = count_df[count_df["model"].isin(order)]
    n_ranks = int(sub_c["freq_rank"].max()) + 1 if len(sub_c) else 1
    heat = np.full((len(order), n_ranks), np.nan)
    for _, r in sub_c.iterrows():
        heat[order.index(r["model"]), int(r["freq_rank"])] = r["median_bout_frames"]

    fig_w = max(8.0, 0.09 * n_ranks + 3.2)
    fig_h = max(4.0, 0.18 * len(order) + 1.8)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(
        heat,
        aspect="auto",
        cmap="magma",
        interpolation="nearest",
        vmin=0,
        vmax=vmax,
    )
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([label_map[m] for m in order], fontsize=6)
    xt = list(range(0, n_ranks, max(1, n_ranks // 20)))
    if (n_ranks - 1) not in xt:
        xt.append(n_ranks - 1)
    ax.set_xticks(xt)
    ax.set_xticklabels([str(t) for t in xt], fontsize=7)
    ax.set_xlabel("Frequency rank (0 = most used)")
    ax.set_ylabel("Animal-local model (id × κ₂)")
    ax.set_title(
        f"Median bout duration (frames) · {sex} · {condition} · K={ss}\n"
        f"absorb <{MIN_BOUT} frames · within-model freq rank"
    )
    cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_label(f"Median bout frames (cmap clipped at {vmax:g})")
    fig.text(
        0.01,
        0.005,
        "nor_per_animal_paramscan · accent QC · D only · shared vmax across 18 panels · "
        "raw_syllable_id not portable (ADR-0005)",
        fontsize=7,
        color="#555",
    )
    stem = f"fig_median_bout_dur_sex-{sex}_tx-{condition}_ss-{ss}"
    pdf = fig_dir / f"{stem}.pdf"
    svg = fig_dir / f"{stem}.svg"
    fig.savefig(pdf)
    fig.savefig(svg)
    plt.close(fig)
    print(f"  wrote {stem}", flush=True)
    return pdf


def write_figures(out: Path) -> None:
    model_df = pd.read_csv(
        out / "model_summary_clean.csv",
        dtype={"kappa1": str, "kappa2": str, "kappa2_label": str, "row_label": str},
    )
    count_df = pd.read_csv(
        out / "syllable_counts_clean.csv",
        dtype={"kappa1": str, "kappa2": str, "kappa2_label": str},
    )
    fig_dir = out / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    vmax = shared_vmax(count_df)
    written: list[str] = []
    for sex in SEXES:
        for condition in CONDITIONS:
            for ss in NUM_STATES:
                path = fig_median_duration_panel(
                    model_df,
                    count_df,
                    sex=sex,
                    condition=condition,
                    ss=ss,
                    vmax=vmax,
                    fig_dir=fig_dir,
                )
                if path is not None:
                    written.append(path.name)

    (fig_dir / "FIGURES.md").write_text(
        f"""# Figures — per-animal accent / duration QC

Dest = slides. Descriptive (D) only.

## Stems

18 panels: `fig_median_bout_dur_sex-{{F|M}}_tx-{{noSD|GHSD|RBSD}}_ss-{{50|75|100}}`

| Axis / encoding | Meaning |
|-----------------|---------|
| y | animal-local model at that `num_states` (animal × κ₂) |
| x | within-model frequency rank (0 = most used) |
| color | median bout duration (frames); shared vmax={vmax:g} |

## Regen

```powershell
uv run python scratch/nor_object_mi/per_animal_descriptives_qc.py --figures-only
```

## What this is not

Not alphabet equating; not a condition I claim; `raw_syllable_id` is not portable.
""",
        encoding="utf-8",
    )
    print(f"Wrote {len(written)} figures -> {fig_dir} (vmax={vmax:g})", flush=True)


def write_info(out: Path) -> None:
    (out / "INFO_syllable_descriptives.md").write_text(
        """# INFO — per-animal syllable descriptives / accent QC

Grain: one inventory row = one animal-local model × `raw_syllable_id` (clean absorb).

## Question (plain)

Do animal-local alphabets show similar median bout-duration structure when syllables
are ranked by within-model frequency, stratified by sex × condition × `num_states`?

## Association

Descriptive (D) only. No test.

## Hit rule

None (QC / accent bearings).

## What this is not

Not cross-animal syllable identity; not DA; not DR×condition.

## Artifacts

| File | Unit |
|------|------|
| `model_summary_clean.csv` | one animal-local model |
| `syllable_counts_clean.csv` | one syllable within one model |
| `figures/fig_median_bout_dur_*.{pdf,svg}` | one sex × condition × K panel |
""",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nor-h5", type=Path, default=DEFAULT_NOR)
    ap.add_argument("--ensemble-root", type=Path, default=DEFAULT_ENSEMBLE)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Default: <ensemble>/_syllable_descriptives",
    )
    ap.add_argument(
        "--figures-only",
        action="store_true",
        help="Skip inventory extract; redraw from existing CSVs",
    )
    args = ap.parse_args(argv)

    out = args.out_dir or (args.ensemble_root / "_syllable_descriptives")
    out.mkdir(parents=True, exist_ok=True)

    if not args.figures_only:
        extract_inventory(args.ensemble_root, args.nor_h5, out)
    write_figures(out)
    write_info(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
