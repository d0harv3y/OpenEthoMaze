#!/usr/bin/env python
"""Three-stream kpMS hypnogram overlay for one trial (scratch).

Maps anatomical / blob / fused ``results_apply.h5`` syllables onto a shared
source ``frame_index`` axis and plots them with legacy ``is_moving`` + speed.

Example::

    uv run python scratch/kpms_ensemble_compare/visualize_three_stream_overlay.py ^
      --trial-key 3243-S01-T01 ^
      --seed 042 ^
      --root C:\\Users\\admin\\Documents\\work\\sack\\test ^
      --out scratch/kpms_ensemble_compare/output/overlays
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import keypoint_moseq as kpms
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import hsv_to_rgb
from matplotlib.patches import Patch

_SCRATCH_DIR = Path(__file__).resolve().parent
if str(_SCRATCH_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_DIR))

from movement_layer import (  # noqa: E402
    load_ambulation_xy,
    movement_series_for_trial,
    syllable_boundaries,
)

STREAMS = ("anatomical", "blob", "fused")
STREAM_COLORS = {
    "anatomical": "#4C9BE8",
    "blob": "#E8A04C",
    "fused": "#9BE84C",
}


def syllable_rgb(sid: int) -> tuple[float, float, float]:
    """Match unified_overlay HSV syllable palette (OpenCV hue 0-180 scaled to 0-1)."""
    if sid < 0:
        return (0.12, 0.12, 0.14)
    hue = (sid * 37 % 180) / 180.0
    return tuple(float(x) for x in hsv_to_rgb((hue, 0.78, 0.86)))


def strip_rgb(ids: np.ndarray, *, height: int = 1) -> np.ndarray:
    """Shape (height, width, 3) RGB image for imshow."""
    w = int(ids.size)
    rgb = np.zeros((height, w, 3), dtype=np.float32)
    for j in range(w):
        rgb[:, j, :] = syllable_rgb(int(ids[j]))
    return rgb


def map_syllables_to_frames(source_frames: np.ndarray, syllable: np.ndarray) -> dict[int, int]:
    out: dict[int, int] = {}
    for f, s in zip(source_frames, syllable, strict=True):
        sid = int(s)
        if sid >= 0:
            out[int(f)] = sid
    return out


def dense_strip(frame_min: int, frame_max: int, mapping: dict[int, int]) -> np.ndarray:
    width = frame_max - frame_min + 1
    arr = np.full(width, -1, dtype=np.int32)
    for f, sid in mapping.items():
        if frame_min <= f <= frame_max:
            arr[f - frame_min] = sid
    return arr


def boundary_frame_positions(source_frames: np.ndarray, syllable: np.ndarray) -> np.ndarray:
    b = syllable_boundaries(np.asarray(syllable))
    if b.size == 0:
        return np.array([], dtype=np.int64)
    return np.asarray(source_frames[b], dtype=np.int64)


def load_stream_syllable(
    root: Path,
    stream: str,
    seed: str,
    trial_key: str,
) -> np.ndarray:
    path = root / stream / f"seed_{seed}" / "results_apply.h5"
    if not path.is_file():
        raise FileNotFoundError(path)
    results = kpms.load_hdf5(str(path))
    if trial_key not in results:
        raise KeyError(f"{trial_key!r} not in {path}")
    return np.asarray(results[trial_key]["syllable"]).ravel()


def render_overlay(
    *,
    root: Path,
    legacy_db: Path,
    manifest_csv: Path,
    trial_key: str,
    seed: str,
    out_path: Path,
    show_boundaries: bool,
    dpi: int,
) -> Path:
    from maze.pipeline.io.file_discovery import load_manifest_csv

    manifest_by_key = {m.kpms_results_dict_key: m for m in load_manifest_csv(manifest_csv)}
    if trial_key not in manifest_by_key:
        raise KeyError(f"Trial {trial_key!r} not in {manifest_csv}")
    manifest = manifest_by_key[trial_key]

    xy = load_ambulation_xy(legacy_db, manifest)
    if xy is None:
        raise FileNotFoundError(f"No ambulation xy for {trial_key} in {legacy_db}")

    amb_fi = np.asarray(xy["frame_index"], dtype=np.int64)
    amb_moving = np.asarray(xy["is_moving"], dtype=np.uint8)
    amb_x = np.asarray(xy["x"], dtype=np.float64)
    amb_y = np.asarray(xy["y"], dtype=np.float64)
    amb_t = np.asarray(xy["t_s"], dtype=np.float64)

    speed = np.zeros(amb_fi.shape[0], dtype=np.float64)
    if amb_fi.size >= 2:
        dt = np.diff(amb_t)
        dt = np.where(dt > 0, dt, np.nan)
        dist = np.hypot(np.diff(amb_x), np.diff(amb_y))
        speed[1:] = np.nan_to_num(dist / dt, nan=0.0)

    frame_min = int(amb_fi.min())
    frame_max = int(amb_fi.max())
    width = frame_max - frame_min + 1
    x_frames = np.arange(frame_min, frame_max + 1)

    stream_data: dict[str, dict] = {}
    for stream in STREAMS:
        syll = load_stream_syllable(root, stream, seed, trial_key)
        mv = movement_series_for_trial(manifest, stream, legacy_db)  # type: ignore[arg-type]
        if mv is None:
            raise RuntimeError(f"Could not align {stream} for {trial_key}")
        if mv.source_frames.shape[0] != syll.shape[0]:
            raise RuntimeError(
                f"{stream}: syllable length {syll.shape[0]} != alignment {mv.source_frames.shape[0]}"
            )
        mapping = map_syllables_to_frames(mv.source_frames, syll)
        strip = dense_strip(frame_min, frame_max, mapping)
        stream_data[stream] = {
            "syllable": syll,
            "source_frames": mv.source_frames,
            "strip": strip,
            "K": len({v for v in mapping.values()}),
            "boundaries": boundary_frame_positions(mv.source_frames, syll),
        }

    moving_strip = np.zeros(width, dtype=np.uint8)
    fi_to_moving = {int(f): int(m) for f, m in zip(amb_fi, amb_moving, strict=True)}
    for j, f in enumerate(x_frames):
        moving_strip[j] = fi_to_moving.get(int(f), 0)

    speed_on_axis = np.array([speed[np.where(amb_fi == f)[0][0]] if np.any(amb_fi == f) else 0.0 for f in x_frames])

    fig_h = 6.5 if show_boundaries else 5.5
    fig, axes = plt.subplots(
        6,
        1,
        figsize=(14, fig_h),
        sharex=True,
        gridspec_kw={"height_ratios": [1, 1, 1, 0.45, 0.45, 1.2]},
    )
    fig.suptitle(f"{trial_key}  |  seed_{seed}  |  3-stream kpMS overlay", fontsize=12, y=0.98)

    for ax, stream in zip(axes[:3], STREAMS, strict=True):
        data = stream_data[stream]
        img = strip_rgb(data["strip"], height=8)
        ax.imshow(img, aspect="auto", interpolation="nearest", extent=(frame_min, frame_max, 0, 1))
        ax.set_yticks([])
        ax.set_ylabel(stream, rotation=0, labelpad=40, va="center", fontweight="bold")
        ax.text(
            0.01,
            0.75,
            f"K={data['K']}  T={len(data['syllable'])}",
            transform=ax.transAxes,
            fontsize=8,
            color="white",
            bbox=dict(facecolor="black", alpha=0.45, pad=2),
        )
        if show_boundaries and data["boundaries"].size:
            for bf in data["boundaries"]:
                ax.axvline(int(bf), color=STREAM_COLORS[stream], alpha=0.35, linewidth=0.6)

    ax_mov = axes[3]
    mov_img = np.zeros((1, width, 3), dtype=np.float32)
    for j in range(width):
        mov_img[0, j] = (0.15, 0.55, 0.25) if moving_strip[j] else (0.25, 0.25, 0.28)
    ax_mov.imshow(mov_img, aspect="auto", interpolation="nearest", extent=(frame_min, frame_max, 0, 1))
    ax_mov.set_yticks([])
    ax_mov.set_ylabel("is_moving", rotation=0, labelpad=40, va="center")

    ax_spd = axes[4]
    ax_spd.fill_between(x_frames, 0, speed_on_axis, color="#888888", alpha=0.35, linewidth=0)
    ax_spd.plot(x_frames, speed_on_axis, color="#DDDDDD", linewidth=0.8)
    ax_spd.set_ylabel("speed\n(m/s)", rotation=0, labelpad=40, va="center", fontsize=8)
    ax_spd.set_yticks([])

    # Boundary coincidence panel: mark frames where 2+ streams change syllable within delta
    ax_agree = axes[5]
    delta = 3
    all_bounds = [stream_data[s]["boundaries"] for s in STREAMS]
    agree_counts = np.zeros(width, dtype=np.int32)
    for j, f in enumerate(x_frames):
        c = 0
        for bounds in all_bounds:
            if bounds.size and np.any(np.abs(bounds - f) <= delta):
                c += 1
        agree_counts[j] = c
    agree_img = np.zeros((1, width, 3), dtype=np.float32)
    for j in range(width):
        c = agree_counts[j]
        if c >= 3:
            agree_img[0, j] = (0.9, 0.9, 0.3)
        elif c == 2:
            agree_img[0, j] = (0.5, 0.5, 0.2)
        else:
            agree_img[0, j] = (0.15, 0.15, 0.17)
    ax_agree.imshow(agree_img, aspect="auto", interpolation="nearest", extent=(frame_min, frame_max, 0, 1))
    ax_agree.set_yticks([])
    ax_agree.set_ylabel("boundary\noverlap", rotation=0, labelpad=40, va="center", fontsize=8)
    ax_agree.set_xlabel("source video frame_index")

    legend_handles = [
        Patch(facecolor=(0.15, 0.55, 0.25), label="is_moving=1"),
        Patch(facecolor=(0.9, 0.9, 0.3), label=f"syllable boundary in 3 streams (@{delta}f)"),
        Patch(facecolor=(0.5, 0.5, 0.2), label=f"boundary in 2 streams (@{delta}f)"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=3, fontsize=8, frameon=False)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0.06, 0.04, 1, 0.95))
    fig.savefig(out_path, dpi=dpi, facecolor="#1a1a1e")
    plt.close(fig)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trial-key", required=True, help="kpMS recording key, e.g. 3243-S01-T01")
    p.add_argument("--seed", default="042", help="Seed folder name suffix (default 042)")
    p.add_argument(
        "--root",
        type=Path,
        default=Path(r"C:\Users\admin\Documents\work\sack\test"),
        help="Ensemble project root (anatomical/, blob/, fused/)",
    )
    p.add_argument(
        "--legacy-db",
        type=Path,
        default=None,
        help="Pipeline H5 with ambulation_metrics (default: <root>/vast_results_legacy.h5)",
    )
    p.add_argument(
        "--manifest-csv",
        type=Path,
        default=None,
        help="kpMS manifest (default: <root>/trial_manifest_kpms_tracking_wsl.csv)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output PNG path (default: scratch/.../output/overlays/<trial>_<seed>.png)",
    )
    p.add_argument(
        "--no-boundaries",
        action="store_true",
        help="Hide per-stream syllable boundary vlines",
    )
    p.add_argument("--dpi", type=int, default=150)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    legacy_db = (args.legacy_db or root / "vast_results_legacy.h5").resolve()
    manifest_csv = (args.manifest_csv or root / "trial_manifest_kpms_tracking_wsl.csv").resolve()
    out = args.out or (
        _SCRATCH_DIR / "output" / "overlays" / f"{args.trial_key.replace('/', '-')}_seed_{args.seed}.png"
    )

    path = render_overlay(
        root=root,
        legacy_db=legacy_db,
        manifest_csv=manifest_csv,
        trial_key=args.trial_key,
        seed=str(args.seed),
        out_path=out.resolve(),
        show_boundaries=not args.no_boundaries,
        dpi=int(args.dpi),
    )
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
