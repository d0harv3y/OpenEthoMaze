"""Prox/Quad shannon–richness figure pack for per-animal paramscan cells.

Mirrors ``fig_prox_quad_comp_violins.py`` / ``simpler_first_prox_quad_comp_figs_min0``
but on animal-local alphabets:

  - consensus = median across 9 ``paramscan_*`` cells (+½ IQR salt whiskers)
  - per-model Kruskal y-axis = fit-parameter cell (not animal-local syllable id)

Syllable IDs are incommensurate across animals; composition scalars (Shannon /
richness / DR) are the comparable objects. Exploratory (#alphabet-bound).

Regen::

    uv run python scratch/nor_object_mi/fig_prox_quad_per_animal_comp_violins.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.fig_prox_quad_comp_violins import (  # noqa: E402
    KIND_YLAB,
    KINDS_DEFAULT,
    ROI_LAB,
    consensus_with_salt,
    fig_consensus_heatmap,
    fig_per_model_heatmap,
    fig_violins,
    kruskal_per_model_role_session,
    kruskal_role_session,
)

DEFAULT_PER_CELL = Path(
    r"D:\sack\datas\impress\nor_per_animal_paramscan"
    r"\_nor_object_mi\simpler_first_prox_quad_per_animal\per_animal_per_cell.csv"
)
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\nor_per_animal_paramscan"
    r"\_nor_object_mi\simpler_first_prox_quad_per_animal_figs"
)

ALPHABET = "per_animal_raw_syllable_id_median_x9"


def _foot_violin(*, roi: str, kind: str) -> str:
    return (
        f"Grain: animal × session × nvl_obj × {ROI_LAB[roi]} ({kind}). "
        "Rows = fam / nvl / DR (object scores are recognition-trial only). "
        "Cols = session. Six violins = condition × sex. "
        "Point = median across 9 per-animal paramscan cells (same s1/s2/ss/ct "
        "grid); whiskers = ±½ across-cell IQR (salt). "
        "Kruskal within sex; * = BH q < 0.05 in the 24-cell role×session×sex "
        "family. "
        "Alphabet: animal-local raw syllable ids — IDs incommensurate; scalars "
        f"compared. Tag: {ALPHABET}."
    )


def _foot_hm_consensus() -> str:
    return (
        "Kruskal on level/DR ~ condition within sex. Color = −log₁₀(uncorrected p), "
        "clip 4; * = BH q < 0.05 within the 24-cell family (role × session × sex). "
        "Trial fixed at nvl_obj. Consensus = median across 9 paramscan cells."
    )


def _foot_hm_model() -> str:
    return (
        "Per-cell Kruskal on level/DR ~ condition within sex. y = paramscan fit "
        "parameters (s1/s2/ss; ct fixed). Panel grid: rows = fam|nvl|DR, cols = sex. "
        "Heatmap x = session. Color = −log₁₀(p), clip 4; * = BH q < 0.05 within "
        "model × role (session × sex). Syllable alphabets are animal-local — "
        "composition scalars only."
    )


def run_board(
    *,
    long: pd.DataFrame,
    out: Path,
    dest: str,
    roi: str,
    kind: str,
    per_cell: pd.DataFrame,
) -> list[Path]:
    family = f"peranimal-consensus-{roi}-{kind}-A"
    kr = kruskal_role_session(long, family=family)
    kr.to_csv(out / f"kruskal_consensus_{roi}_{kind}.csv", index=False)
    long.to_csv(out / f"long_consensus_{roi}_{kind}.csv", index=False)
    paths: list[Path] = []
    paths.append(
        fig_violins(
            long,
            kr,
            out / "figures",
            dest=dest,
            stem=f"fig_consensus_{roi}_{kind}_violins",
            title=(
                f"{KIND_YLAB[kind]} · {ROI_LAB[roi]}  "
                f"(per-animal median×9 cells + salt)"
            ),
            footnote=_foot_violin(roi=roi, kind=kind),
            ylab=KIND_YLAB[kind],
            zero_line=True,
        )
    )
    paths.append(
        fig_consensus_heatmap(
            kr,
            out / "figures",
            dest=dest,
            stem=f"fig_consensus_{roi}_{kind}_kruskal_heatmap",
            title=(
                f"Kruskal ~ condition  ({KIND_YLAB[kind]} · {ROI_LAB[roi]} · "
                f"per-animal consensus)"
            ),
            footnote=_foot_hm_consensus(),
        )
    )
    kr_m, labels = kruskal_per_model_role_session(per_cell, roi=roi, kind=kind)
    if not kr_m.empty:
        kr_m.to_csv(out / f"kruskal_per_model_{roi}_{kind}.csv", index=False)
        labels.to_csv(out / f"model_labels_{roi}_{kind}.csv", index=False)
        paths.append(
            fig_per_model_heatmap(
                kr_m,
                labels,
                out / "figures",
                dest=dest,
                stem=f"fig_per_model_{roi}_{kind}_kruskal_heatmap",
                title=(
                    f"Per-paramscan-cell Kruskal ~ condition  "
                    f"({KIND_YLAB[kind]} · {ROI_LAB[roi]} · per-animal fits)"
                ),
                footnote=_foot_hm_model(),
            )
        )
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-cell-csv", type=Path, default=DEFAULT_PER_CELL)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument(
        "--kinds",
        type=str,
        default=",".join(KINDS_DEFAULT),
        help="Comma-separated kinds: shannon,richness,hill2",
    )
    args = ap.parse_args(argv)
    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
    for k in kinds:
        if k not in KIND_YLAB:
            raise ValueError(f"unknown kind {k!r}; expected one of {tuple(KIND_YLAB)}")

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)

    per_cell = pd.read_csv(args.per_cell_csv)
    need = {
        "animal_id",
        "sex",
        "condition",
        "session",
        "model",
        "contrast_eligible_quad",
        "contrast_eligible_prox",
    }
    missing = sorted(need - set(per_cell.columns))
    if missing:
        raise KeyError(f"per_animal_per_cell missing {missing}")

    n_models = int(per_cell["model"].nunique())
    print(
        f"per-animal cells: n_rows={len(per_cell)} n_models={n_models} "
        f"n_animals={per_cell['animal_id'].nunique()}",
        flush=True,
    )

    preview: list[Path] = []
    for roi in ("quad", "prox"):
        for kind in kinds:
            print(f"=== consensus+salt {roi} {kind} ===", flush=True)
            long_m = consensus_with_salt(per_cell, roi=roi, kind=kind)
            # retag alphabet for clarity in long tables
            long_m = long_m.copy()
            long_m["alphabet"] = ALPHABET
            preview.extend(
                run_board(
                    long=long_m,
                    out=out,
                    dest=args.dest,
                    roi=roi,
                    kind=kind,
                    per_cell=per_cell,
                )
            )

    index = out / "preview_paths.txt"
    index.write_text("\n".join(str(p) for p in preview) + "\n", encoding="utf-8")
    print(f"done -> {out}  ({len(preview)} preview pngs)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
