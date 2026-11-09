"""Ethogram: Davis scorer vs Sturman-transfer MLP raters (one video)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CLASS_COLORS = {
    "None": "#7f7f7f",
    "Supported": "#2ca02c",
    "Unsupported": "#d62728",
    "Grooming": "#ff7f0e",
    "": "#1a1a1a",
    "unlabeled": "#1a1a1a",
    "nan": "#7f7f7f",  # pandas round-trips class name None → NaN
}


def _as_class_labels(series: pd.Series) -> np.ndarray:
    """Map CSV labels; pandas reads the class name ``None`` as NaN."""
    s = series.astype("string")
    out = s.fillna("None").astype(str).to_numpy()
    out = np.where(np.isin(out, ("nan", "<NA>", "None")), "None", out)
    # keep explicit None class; only empty → None
    return out


def _paint_strip(ax, frames: np.ndarray, labels: np.ndarray, *, ylabel: str) -> None:
    """Draw 1-row ethogram; ``frames`` absolute indices, ``labels`` class strings."""
    ax.set_xlim(frames[0], frames[-1] + 1)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.5])
    ax.set_yticklabels([ylabel], fontsize=9)
    ax.set_xticks([])
    # run-length encode for fewer rectangles
    i = 0
    n = len(labels)
    while i < n:
        j = i + 1
        while j < n and labels[j] == labels[i]:
            j += 1
        lab = str(labels[i])
        color = CLASS_COLORS.get(lab, "#9467bd")
        ax.axvspan(frames[i], frames[j - 1] + 1, facecolor=color, edgecolor="none", alpha=0.95)
        i = j
    ax.tick_params(axis="y", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)


def plot_ethogram(
    pred_dir: Path,
    *,
    video_id: str,
    experimenters: tuple[str, ...] = ("Furkan", "Jin", "Oliver"),
    davis_scorer: str = "DOH",
    fps: float = 29.55,
    out_path: Path | None = None,
) -> Path:
    rows: list[tuple[str, np.ndarray, np.ndarray]] = []
    ref: pd.DataFrame | None = None
    for exp in experimenters:
        path = pred_dir / f"pred_{video_id}_{exp}.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        df = pd.read_csv(path)
        if ref is None:
            ref = df
            frames = df["frame"].to_numpy(dtype=int)
            covered = df["covered"].to_numpy(dtype=int).astype(bool)
            y_true = _as_class_labels(df["y_true"])
            doh = np.where(covered, y_true, "unlabeled")
            rows.append((f"{davis_scorer} (human)", frames, doh))
        rows.append(
            (f"MLP←{exp}", df["frame"].to_numpy(dtype=int), _as_class_labels(df["y_pred"]))
        )

    n = len(rows)
    fig, axes = plt.subplots(
        n + 1,
        1,
        figsize=(14, 1.1 * n + 1.2),
        gridspec_kw={"height_ratios": [1] * n + [0.55], "hspace": 0.15},
        sharex=False,
    )
    for ax, (name, frames, labs) in zip(axes[:-1], rows, strict=True):
        _paint_strip(ax, frames, labs, ylabel=name)

    # time axis on bottom
    ax_t = axes[-1]
    frames0 = rows[0][1]
    t0, t1 = frames0[0] / fps, (frames0[-1] + 1) / fps
    ax_t.set_xlim(t0, t1)
    ax_t.set_ylim(0, 1)
    ax_t.set_yticks([])
    ax_t.set_xlabel(f"time (s)  ·  {video_id}  ·  fps={fps:.2f}")
    for spine in ("top", "left", "right"):
        ax_t.spines[spine].set_visible(False)
    # sync x of ethogram rows to frame numbers matching time
    for ax in axes[:-1]:
        ax.set_xlim(frames0[0], frames0[-1] + 1)

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=CLASS_COLORS[c], label=c)
        for c in ("Supported", "Unsupported", "Grooming", "None", "unlabeled")
    ]
    fig.legend(handles=handles, loc="upper center", ncol=5, fontsize=9, frameon=False)
    fig.suptitle(
        f"Ethogram — {video_id}: Davis {davis_scorer} vs Sturman-transfer MLPs",
        fontsize=12,
        y=0.98,
    )

    out_path = out_path or (pred_dir / f"ethogram_{video_id.replace(' ', '_')}.png")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", facecolor="white")
    pdf = out_path.with_suffix(".pdf")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out_path}", flush=True)
    print(f"wrote {pdf}", flush=True)
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--pred-dir",
        type=Path,
        default=_ROOT / "runs" / "davis_transfer",
    )
    p.add_argument("--video-id", type=str, default="Test 42")
    p.add_argument("--davis-scorer", type=str, default="DOH")
    p.add_argument("--fps", type=float, default=29.55)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)
    plot_ethogram(
        args.pred_dir,
        video_id=args.video_id,
        davis_scorer=args.davis_scorer,
        fps=args.fps,
        out_path=args.out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
