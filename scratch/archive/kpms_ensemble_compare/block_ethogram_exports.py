#!/usr/bin/env python3
"""Block-stratified kpMS ethogram composites (scratch).

Mirrors block dwell export layout (sex × strain × tx, trial blocks, per-session /
trial1-9 / all-sessions) with extra nesting per pose stream and fit seed.

Each PNG (separate ``_run`` / ``_iti`` files) stacks:
  1. Stacked syllable bars (height = n(t); jet colors; global-occupancy stack order)
  2. Mean global-occupancy line ± SEM across trials
  3. Syllable entropy line ± bootstrap SEM across trials

Time axis: **0.333 s** bins from phase onset; shorter trials NaN-pad; bar height encodes n(t).
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

import h5py
import keypoint_moseq as kpms
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.io.file_discovery import load_manifest_csv
from maze.pipeline.viz.block_dwell_average import (
    ALL_TRIAL_BLOCKS,
    FULL_SESSION_BLOCK,
    POOLED_SESSION_LABEL,
    TRIAL_BLOCKS,
    export_relpath,
    tx_path_token,
)

_SCRATCH_DIR = Path(__file__).resolve().parent
if str(_SCRATCH_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRATCH_DIR))

from movement_layer import load_ambulation_xy, movement_series_for_trial  # noqa: E402

STREAMS = ("anatomical", "blob", "fused")
SEEDS = ("005", "013", "042", "067", "111")
PhaseKind = Literal["run", "iti"]
BIN_SECONDS = 1.0 / 3.0
ENTROPY_BOOTSTRAP_ITERS = 100
_ENTROPY_RNG = np.random.default_rng(0)

SUMMARY_FIELDS = (
    "stream",
    "seed",
    "phase",
    "session",
    "tx",
    "sex",
    "strain",
    "block",
    "block_trials",
    "n_trials",
    "max_phase_seconds",
    "output_path",
)


def syllable_jet_rgb(sid: int, *, max_syllable_id: int) -> tuple[float, float, float]:
    if sid < 0 or not np.isfinite(sid):
        return (0.12, 0.12, 0.14)
    denom = max(int(max_syllable_id), 1)
    t = float(int(sid)) / float(denom)
    return tuple(float(x) for x in cm.jet(t)[:3])


@dataclass(frozen=True)
class ModelPlotLimits:
    max_syllable_id: int
    occ_ymax: float
    ent_ymax: float
    stack_order: tuple[int, ...]
    speed_rank: dict[int, int] | None = None


def _jet_for_syllable(sid: int, limits: ModelPlotLimits) -> tuple[float, float, float]:
    if limits.speed_rank is not None:
        idx = limits.speed_rank.get(int(sid), 0)
        max_idx = max(limits.speed_rank.values()) if limits.speed_rank else 1
        return syllable_jet_rgb(idx, max_syllable_id=max_idx)
    return syllable_jet_rgb(sid, max_syllable_id=limits.max_syllable_id)


def model_plot_limits(
    global_occ: dict[int, float],
    *,
    speed_rank: dict[int, int] | None = None,
) -> ModelPlotLimits:
    if not global_occ:
        return ModelPlotLimits(0, 1.0, 1.0, (), speed_rank)
    max_id = max(global_occ.keys())
    occ_ymax = max(global_occ.values())
    ent_ymax = math.log(len(global_occ)) if len(global_occ) > 1 else 1.0
    if speed_rank is not None:
        order = tuple(sorted(global_occ.keys(), key=lambda s: (speed_rank.get(s, 10**9), s)))
        max_id = max(speed_rank.values()) if speed_rank else max_id
    else:
        order = tuple(sorted(global_occ.keys(), key=lambda s: (global_occ[s], s)))
    return ModelPlotLimits(max_id, occ_ymax, ent_ymax, order, speed_rank)


def load_speed_rank_table(path: Path) -> dict[int, int]:
    df = pd.read_csv(path)
    return {int(r.raw_syllable_id): int(r.speed_index) for r in df.itertuples(index=False)}


def _entropy_from_labels(labels: np.ndarray) -> float:
    if labels.size == 0:
        return float("nan")
    _, counts = np.unique(labels.astype(np.int64), return_counts=True)
    p = counts / counts.sum()
    return float(-np.sum(p * np.log(p + 1e-12)))


def _entropy_with_sem(labels: np.ndarray) -> tuple[float, float]:
    valid = labels[np.isfinite(labels)].astype(np.int64)
    if valid.size == 0:
        return float("nan"), float("nan")
    if valid.size == 1:
        return 0.0, 0.0
    ent = _entropy_from_labels(valid)
    boots = [
        _entropy_from_labels(_ENTROPY_RNG.choice(valid, size=valid.size, replace=True))
        for _ in range(ENTROPY_BOOTSTRAP_ITERS)
    ]
    return ent, float(np.std(boots, ddof=1))


def _decode_state(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode().strip()
    return str(value).strip()


def _load_manifest_rows(
    manifest_path: Path,
    *,
    phase: str,
    researcher: str,
    sessions: Sequence[str],
) -> pd.DataFrame:
    df = pd.read_csv(manifest_path, keep_default_na=False)
    mask = (
        (df["phase"].astype(str) == phase)
        & (df["session"].isin(sessions))
        & (df["researcher"].astype(str) == researcher)
    )
    sub = df.loc[mask].copy()
    for col in ("sex", "strain", "tx"):
        sub = sub[sub[col].astype(str).str.strip() != ""]
        sub = sub[sub[col].astype(str) != "?"]
    return sub


def _parse_sessions(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ("S01", "S02", "S03", "S04", "S05")
    return tuple(s.strip() for s in raw.split(",") if s.strip())


def _parse_blocks(raw: str | None, *, valid: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    if not raw:
        return tuple(valid.keys())
    blocks = tuple(b.strip() for b in raw.split(",") if b.strip())
    unknown = [b for b in blocks if b not in valid]
    if unknown:
        raise ValueError(f"Unknown block(s): {', '.join(unknown)}")
    return blocks


def _parse_models(raw: list[str] | None) -> list[tuple[str, str]]:
    if not raw:
        return [(s, seed) for s in STREAMS for seed in SEEDS]
    out: list[tuple[str, str]] = []
    for item in raw:
        stream, seed = item.split("/", 1)
        seed = seed.replace("seed_", "")
        if len(seed) == 3 and seed.isdigit():
            pass
        elif seed.startswith("seed_"):
            seed = seed[5:]
        out.append((stream, seed.zfill(3)))
    return out


def build_global_occupancy(results_path: Path) -> dict[int, float]:
    data = kpms.load_hdf5(str(results_path))
    counts: Counter[int] = Counter()
    total = 0
    for rec in data.values():
        syll = np.asarray(rec.get("syllable", [])).ravel()
        valid = syll[syll >= 0]
        for s in valid.astype(int):
            counts[int(s)] += 1
            total += 1
    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def _frame_to_state(xy: np.ndarray) -> dict[int, str]:
    out: dict[int, str] = {}
    for row in xy:
        out[int(row["frame_index"])] = _decode_state(row["trial_state"])
    return out


def _trial_fps(h5: h5py.File, animal_id: int, session: str, trial: str) -> float:
    path = f"{animal_id}/{session}/{trial}"
    if path not in h5:
        return 30.0
    fps = float(h5[path].attrs.get("fps", 30.0))
    return fps if fps > 0 else 30.0


def trial_phase_syllable_by_bin(
    syllable: np.ndarray,
    source_frames: np.ndarray,
    frame_to_state: dict[int, str],
    *,
    phase: PhaseKind,
    fps: float,
) -> np.ndarray | None:
    """Per-trial mode syllable id in each 0.333 s bin from phase onset (NaN if absent)."""
    syllable = np.asarray(syllable).ravel()
    source_frames = np.asarray(source_frames, dtype=np.int64).ravel()
    if syllable.size != source_frames.size or syllable.size == 0:
        return None

    states = np.array([frame_to_state.get(int(f), "") for f in source_frames], dtype=object)
    if phase == "run":
        mask = states == "run"
    else:
        mask = states != "run"
    if not np.any(mask):
        return None

    sf = source_frames[mask]
    sy = syllable[mask]
    onset = int(sf.min())
    bin_idx = np.floor((sf.astype(np.float64) - onset) / (fps * BIN_SECONDS)).astype(np.int64)
    max_bin = int(bin_idx.max())
    out = np.full(max_bin + 1, np.nan, dtype=np.float64)
    for b in range(max_bin + 1):
        in_bin = bin_idx == b
        if not np.any(in_bin):
            continue
        chunk = sy[in_bin]
        chunk = chunk[chunk >= 0]
        if chunk.size == 0:
            continue
        vals, counts = np.unique(chunk.astype(np.int64), return_counts=True)
        out[b] = float(vals[int(np.argmax(counts))])
    return out


@dataclass(frozen=True)
class AggregateBinSeries:
    syllable_counts: np.ndarray
    mean_occupancy: np.ndarray
    sem_occupancy: np.ndarray
    mean_entropy: np.ndarray
    sem_entropy: np.ndarray
    n_trials: np.ndarray
    max_bins: int


def aggregate_trial_bins(
    trial_series: list[np.ndarray],
    global_occ: dict[int, float],
    stack_order: Sequence[int],
) -> AggregateBinSeries | None:
    if not trial_series or not stack_order:
        return None
    max_bin = max(int(s.size) - 1 for s in trial_series)
    width = max_bin + 1
    sid_to_col = {int(s): i for i, s in enumerate(stack_order)}
    padded = np.full((len(trial_series), width), np.nan, dtype=np.float64)
    for i, series in enumerate(trial_series):
        padded[i, : series.size] = series

    n_trials = np.sum(np.isfinite(padded), axis=0).astype(np.int32)
    counts = np.zeros((width, len(stack_order)), dtype=np.int32)
    mean_occ = np.full(width, np.nan, dtype=np.float64)
    sem_occ = np.full(width, np.nan, dtype=np.float64)
    mean_ent = np.full(width, np.nan, dtype=np.float64)
    sem_ent = np.full(width, np.nan, dtype=np.float64)

    for b in range(width):
        col = padded[:, b]
        valid = col[np.isfinite(col)].astype(np.int64)
        if valid.size == 0:
            continue
        for sid in valid:
            j = sid_to_col.get(int(sid))
            if j is not None:
                counts[b, j] += 1
        occ = np.array([global_occ.get(int(v), 0.0) for v in valid], dtype=np.float64)
        mean_occ[b] = float(np.mean(occ))
        sem_occ[b] = float(np.std(occ, ddof=1) / np.sqrt(occ.size)) if occ.size > 1 else 0.0
        ent, ent_sem = _entropy_with_sem(col)
        mean_ent[b] = ent
        sem_ent[b] = ent_sem

    return AggregateBinSeries(
        syllable_counts=counts,
        mean_occupancy=mean_occ,
        sem_occupancy=sem_occ,
        mean_entropy=mean_ent,
        sem_entropy=sem_ent,
        n_trials=n_trials,
        max_bins=max_bin,
    )


def _bin_left_edges(n_bins: int) -> np.ndarray:
    return np.arange(n_bins, dtype=np.float64) * BIN_SECONDS


def _draw_stacked_syllable_bars(
    ax: plt.Axes,
    syllable_counts: np.ndarray,
    *,
    limits: ModelPlotLimits,
) -> None:
    """Edge-aligned stacked bars with full bin width (no inter-bin gaps)."""
    n_bins = syllable_counts.shape[0]
    x = _bin_left_edges(n_bins)
    bottom = np.zeros(n_bins, dtype=np.float64)
    for j, sid in enumerate(limits.stack_order):
        seg = syllable_counts[:, j].astype(np.float64)
        if not np.any(seg):
            continue
        ax.bar(
            x,
            seg,
            width=BIN_SECONDS,
            bottom=bottom,
            color=_jet_for_syllable(sid, limits),
            linewidth=0,
            edgecolor="none",
            align="edge",
        )
        bottom += seg


def render_block_ethogram(
    agg: AggregateBinSeries,
    *,
    limits: ModelPlotLimits,
    title: str,
    out_path: Path,
    dpi: int = 120,
) -> None:
    n_bins = agg.n_trials.size
    x = (np.arange(n_bins) + 0.5) * BIN_SECONDS
    fig, axes = plt.subplots(
        3,
        1,
        figsize=(14, 6.0),
        sharex=True,
        gridspec_kw={"height_ratios": [1.4, 1.0, 1.0]},
    )

    ax0 = axes[0]
    _draw_stacked_syllable_bars(ax0, agg.syllable_counts, limits=limits)
    ax0.set_ylabel("n(t)", fontsize=8)
    ax0.set_ylim(0, max(1, int(agg.n_trials.max()) * 1.05))
    ax0.set_title("syllable composition (stacked by global occupancy)", fontsize=8, loc="left")

    ax1 = axes[1]
    ax1.errorbar(
        x,
        agg.mean_occupancy,
        yerr=agg.sem_occupancy,
        fmt="-",
        color="#333333",
        ecolor="#666666",
        elinewidth=0.8,
        capsize=2,
        markersize=2,
    )
    ax1.set_ylabel("mean occ", fontsize=8)
    ax1.set_ylim(0, limits.occ_ymax * 1.05 if limits.occ_ymax > 0 else 1.0)

    ax2 = axes[2]
    ax2.errorbar(
        x,
        agg.mean_entropy,
        yerr=agg.sem_entropy,
        fmt="-",
        color="#333333",
        ecolor="#666666",
        elinewidth=0.8,
        capsize=2,
        markersize=2,
    )
    ax2.set_ylabel("entropy", fontsize=8)
    ax2.set_xlabel("seconds from phase onset")
    ax2.set_ylim(0, limits.ent_ymax * 1.05 if limits.ent_ymax > 0 else 1.0)

    ax2.set_xlim(0, n_bins * BIN_SECONDS)
    fig.suptitle(title, fontsize=11, y=0.98)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)


DATA_DICTIONARY_FILENAME = "DATA_DICTIONARY.md"
LEGEND_FILENAME = "legend.png"

OVERVIEW_PARAGRAPH = """\
These block ethogram composites summarize keypoint-MoSeq syllable dynamics for the Emma|Hayden \
experimental cohort (sessions S01–S05), stratified by sex × strain × treatment (tx) and trial \
block (T01–T03, T04–T06, T07–T09, or full T01–T09), with optional cross-session pooling \
(session=ALL). Each PNG is scoped to one pose stream, one fit seed, and one behavioral phase \
file suffix: `_run` (legacy `trial_state == run`) or `_iti` (all non-run states). Trials are \
aligned to **0.333 s bins** from phase onset; within each trial and bin the **mode syllable** \
(majority of labeled frames) is assigned. The top panel is a **stacked bar chart**: bar height \
equals **n(t)** (trials contributing at that bin); segments are trial counts per syllable, \
stacked **rarest→most common** by that model's dataset-wide global occupancy. Syllable colors \
use **matplotlib jet** indexed by `syllable_id / max_syllable_id` for that stream/seed. Rows 2–3 \
are **line plots** with error bars: mean per-trial **global occupancy** (syllable prevalence in \
the model's full apply cohort) ± **SEM across trials**, and cross-trial **syllable entropy** \
± **bootstrap SEM** (100 resamples). Y-axis limits are **fixed per model**: occupancy \
`[0, max global weight]`; entropy `[0, ln(# syllables in model)]`. Shorter trials leave \
empty bins at the right; bar height encodes dropout directly.\
"""


def write_global_data_dictionary(out_dir: Path) -> Path:
    """Write ``DATA_DICTIONARY.md`` at the export root (shared across all models)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / DATA_DICTIONARY_FILENAME
    body = f"""# Block ethogram exports — data dictionary

## Overview

{OVERVIEW_PARAGRAPH}

## Figure layout (top → bottom)

| Row | Label | Encoding | Definition |
|-----|-------|----------|------------|
| 1 | **syllable stack** | Stacked bars, jet colors | Per 0.333 s bin: height = n(t); each segment = trials whose mode syllable equals that ID. Stack order: global occupancy ascending (rare bottom). Colors: `jet(syllable_id / max_id)` for this stream/seed. |
| 2 | **mean occ** | Line ± SEM | Mean across trials of global-occupancy weight for each trial's mode syllable in the bin. Y-axis fixed to `[0, max global weight]` for the model. |
| 3 | **entropy** | Line ± bootstrap SEM | Shannon entropy (nats) of syllable-ID distribution across trials at the bin. Error bar = std of 100 bootstrap resamples. Y-axis fixed to `[0, ln(# syllables in model)]`. |

## Time resolution

- Bin width: **0.333 s** (`1/3` second).
- X-axis: seconds from phase onset (bin centers plotted at `(i + ½) × 0.333`).

## Missing data

| Visual | Meaning |
|--------|---------|
| Zero-height bar / gap in lines | No trial contributed at that bin. |
| Skipped stratum/block | No trials passed kpMS + legacy alignment filters; no PNG written. |

## File naming

Per-session tree (mirrors block dwell exports):

```
{{out}}/{{stream}}/seed_{{NNN}}/S##/{{tx_token}}/S##_{{tx_token}}_{{strain}}_{{sex}}_trial{{lo}}-{{hi}}_{{run|iti}}.png
```

- `tx_token`: manifest `tx` with `/` → `_` (e.g. `n/a` → `n_a`).
- Pooled cross-session: `{{out}}/{{stream}}/seed_{{NNN}}/all-sessions/...` with `ALL_` session prefix.
- Full session block: `trial1-9/` subfolder, block `1-9`.

## `summary.csv` columns

| Column | Description |
|--------|-------------|
| `stream` | Pose stream: `anatomical`, `blob`, or `fused`. |
| `seed` | Fit/apply seed (`005`, `013`, …). |
| `phase` | `run` or `iti`. |
| `session` | `S01`–`S05` or `ALL` (pooled). |
| `tx`, `sex`, `strain` | Manifest strata labels. |
| `block` | `1-3`, `4-6`, `7-9`, or `1-9`. |
| `block_trials` | Trial IDs included in block (e.g. `T01,T02,T03`). |
| `n_trials` | Trials that contributed at least one valid phase second. |
| `max_phase_seconds` | Longest aligned phase duration in the stratum (seconds; `max_bin × 0.333`). |
| `output_path` | Absolute path to PNG. |

## Companion artifacts

| File | Purpose |
|------|---------|
| `{LEGEND_FILENAME}` (export root) | Generic reference when no model context is available. |
| `{{stream}}/seed_{{NNN}}/{LEGEND_FILENAME}` | **Per-model** jet scale, stack order, and y-axis limits for that stream/seed. |
| `{DATA_DICTIONARY_FILENAME}` | This document. |

### Speed-ranked coloring (`--speed-reindex`)

Run `syllable_speed_cluster.py` first. Per-model (default) writes
`{{stream}}/seed_{{NNN}}/speed_rank_table.csv` (or `speed_rank_table_{{phase}}.csv`).
**Per-stream** (`--scope per-stream`) pools all seeds, writes canonical tables under
`{{stream}}/shared/` and **projects** per-seed `speed_rank_table*.csv` into each
`seed_{{NNN}}/` folder for ethogram `--speed-reindex`. Jet color and stack order use
`speed_index` (0 = slowest) from that CSV; raw syllable IDs are unchanged in H5.

| Clustering artifact | Scope | Location |
|---------------------|-------|----------|
| `speed_rank_table*.csv` | per-model | `{{stream}}/seed_{{NNN}}/` |
| `speed_rank_table*.csv` (canonical) | per-stream | `{{stream}}/shared/` |
| `speed_rank_table*.csv` (projected) | per-stream | `{{stream}}/seed_{{NNN}}/` |
| `hdbscan_labels*.csv` | both | model dir or `{{stream}}/shared/` |
| `cluster_inequality*.csv` | both | model dir or `{{stream}}/shared/` |
| `speed_motif_grid*.png` | both | model dir or `{{stream}}/shared/` |
| `cluster_run*.json` | per-stream | `{{stream}}/shared/` — seeds included/skipped, `T_max` |

## Related scripts

- Generator: `scratch/kpms_ensemble_compare/block_ethogram_exports.py`
- Speed rank + HDBSCAN: `scratch/kpms_ensemble_compare/syllable_speed_cluster.py` (`--scope per-model|per-stream`)
- Single-trial 3-stream overlay: `scratch/kpms_ensemble_compare/visualize_three_stream_overlay.py`
- Block dwell analogue: `uv run maze-average-block-dwell-plots`
"""
    path.write_text(body, encoding="utf-8")
    return path


def render_global_legend(
    out_path: Path,
    *,
    limits: ModelPlotLimits | None = None,
    model_label: str | None = None,
    dpi: int = 140,
) -> Path:
    """Render a standalone color/scale reference PNG (not duplicated on each stratum plot)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lim = limits or ModelPlotLimits(99, 0.2, math.log(100), tuple(range(100)))
    title = (
        f"Block ethogram — {model_label}"
        if model_label
        else "Block ethogram exports — global legend"
    )

    fig = plt.figure(figsize=(11, 7))
    gs = fig.add_gridspec(4, 1, height_ratios=[0.6, 1.3, 1.0, 1.0], hspace=0.5)
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)

    ax0 = fig.add_subplot(gs[0, 0])
    sample_ids = np.arange(min(lim.max_syllable_id + 1, 100), dtype=np.int32)
    if sample_ids.size == 0:
        sample_ids = np.arange(24, dtype=np.int32)
    jet_strip = np.array(
        [syllable_jet_rgb(int(s), max_syllable_id=lim.max_syllable_id) for s in sample_ids],
        dtype=np.float32,
    ).reshape(1, -1, 3)
    ax0.imshow(jet_strip, aspect="auto", interpolation="nearest", extent=(0, sample_ids.size, 0, 1))
    ax0.set_xlim(0, sample_ids.size)
    ax0.set_yticks([])
    ax0.set_xlabel(
        f"Syllable ID — jet(syllable_id / {lim.max_syllable_id}); stack order = global occupancy ↑"
    )

    ax1 = fig.add_subplot(gs[1, 0])
    demo_bins = 12
    demo_nt = np.array([10, 10, 10, 9, 9, 8, 8, 7, 6, 5, 4, 3], dtype=float)
    demo_sids = lim.stack_order[:4] if len(lim.stack_order) >= 4 else (0, 1, 2, 3)
    fracs = [0.15, 0.25, 0.35, 0.25]
    demo_counts = np.zeros((demo_bins, len(demo_sids)), dtype=np.float64)
    for j, frac in enumerate(fracs):
        demo_counts[:, j] = demo_nt * frac
    _draw_stacked_syllable_bars(
        ax1,
        demo_counts,
        limits=ModelPlotLimits(
            lim.max_syllable_id,
            lim.occ_ymax,
            lim.ent_ymax,
            tuple(int(s) for s in demo_sids),
        ),
    )
    ax1.set_ylabel("n(t)")
    ax1.set_title("Stacked syllables (row 1) — height = contributing trials", fontsize=10, loc="left")
    ax1.set_xlim(0, demo_bins * BIN_SECONDS)

    ax2 = fig.add_subplot(gs[2, 0])
    t = np.linspace(0, demo_bins * BIN_SECONDS, demo_bins)
    y = 0.05 + 0.03 * np.sin(t)
    err = 0.01 + 0.005 * np.cos(t)
    ax2.errorbar(t, y, yerr=err, fmt="-", capsize=2, color="#333333")
    ax2.set_ylabel("mean occ")
    ax2.set_ylim(0, lim.occ_ymax * 1.1)
    ax2.set_title(f"Mean occupancy ± SEM (row 2); y ∈ [0, {lim.occ_ymax:.3f}]", fontsize=10, loc="left")

    ax3 = fig.add_subplot(gs[3, 0])
    y2 = 0.8 + 0.4 * np.sin(t / 2)
    err2 = 0.08 + 0.03 * np.cos(t)
    ax3.errorbar(t, y2, yerr=err2, fmt="-", capsize=2, color="#333333")
    ax3.set_ylabel("entropy")
    ax3.set_xlabel("seconds from phase onset (0.333 s bins)")
    ax3.set_ylim(0, lim.ent_ymax * 1.1)
    ax3.set_title(f"Entropy ± bootstrap SEM (row 3); y ∈ [0, {lim.ent_ymax:.2f}]", fontsize=10, loc="left")

    fig.text(
        0.5,
        0.02,
        "See DATA_DICTIONARY.md for cohort filters, file naming, and summary.csv fields.",
        ha="center",
        fontsize=9,
        style="italic",
    )
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_path


def write_global_artifacts(
    out_dir: Path,
    *,
    limits: ModelPlotLimits | None = None,
) -> tuple[Path, Path]:
    """Write shared legend + data dictionary under the export root."""
    md_path = write_global_data_dictionary(out_dir)
    legend_path = render_global_legend(out_dir / LEGEND_FILENAME, limits=limits)
    return md_path, legend_path


def _phase_suffix(phase: PhaseKind) -> str:
    return phase


def _export_basename(session: str, tx: str, strain: str, sex: str, block: str, phase: PhaseKind) -> str:
    lo, hi = block.split("-", 1)
    tx_tok = tx_path_token(tx)
    return f"{session}_{tx_tok}_{strain}_{sex}_trial{lo}-{hi}_{_phase_suffix(phase)}.png"


def _export_relpath_ethogram(
    session: str,
    tx: str,
    strain: str,
    sex: str,
    block: str,
    phase: PhaseKind,
    *,
    pooled: bool,
) -> Path:
    if pooled:
        return Path(tx_path_token(tx)) / _export_basename(
            POOLED_SESSION_LABEL, tx, strain, sex, block, phase
        )
    return export_relpath(session, tx, strain, sex, block).parent / _export_basename(
        session, tx, strain, sex, block, phase
    )


def run_block_ethogram_exports(
    *,
    kpms_root: Path,
    legacy_db: Path,
    manifest_path: Path,
    out_dir: Path,
    stream: str,
    seed: str,
    phases: Sequence[PhaseKind],
    phase_filter: str = "experimental",
    researcher: str = "Emma|Hayden",
    sessions: Sequence[str] = ("S01", "S02", "S03", "S04", "S05"),
    blocks: Sequence[str] = tuple(TRIAL_BLOCKS.keys()),
    group_by_session: bool = True,
    tracking_h5: Path | None = None,
    speed_reindex: bool = False,
    speed_rank_dir: Path | None = None,
) -> list[dict[str, object]]:
    manifest_df = _load_manifest_rows(
        manifest_path,
        phase=phase_filter,
        researcher=researcher,
        sessions=sessions,
    )
    if manifest_df.empty:
        return []

    all_manifests = {m.kpms_results_dict_key: m for m in load_manifest_csv(manifest_path)}
    results_path = kpms_root / stream / f"seed_{seed}" / "results_apply.h5"
    if not results_path.is_file():
        raise FileNotFoundError(results_path)

    global_occ = build_global_occupancy(results_path)
    rank_root = speed_rank_dir or out_dir
    results = kpms.load_hdf5(str(results_path))
    track_db = tracking_h5 or (kpms_root / "kpms_tracking.h5")

    pre_cfg = KpmsPreprocessConfig(
        min_fragment_frames=4,
        jump_filter_cm=15.0,
        jump_filter_lookahead_frames=3,
        px_per_cm=2.42,
        retain_all_frames=False,
        db_path=track_db,
        pose_stream=stream,  # type: ignore[arg-type]
    )

    summary_rows: list[dict[str, object]] = []
    block_set = set(blocks)
    groups: dict[tuple[str, ...], list[tuple[int, str, str]]] = defaultdict(list)
    for row in manifest_df.itertuples(index=False):
        trial = str(row.trial)
        for block, trials in ALL_TRIAL_BLOCKS.items():
            if block not in block_set:
                continue
            if trial in trials:
                if group_by_session:
                    key = (str(row.session), str(row.tx), str(row.sex), str(row.strain), block)
                else:
                    key = (str(row.tx), str(row.sex), str(row.strain), block)
                groups[key].append((int(row.animal_id), str(row.session), trial))

    with h5py.File(legacy_db, "r") as h5:
        for key, members in sorted(groups.items()):
            if group_by_session:
                session, tx, sex, strain, block = key
                pooled = False
            else:
                tx, sex, strain, block = key
                session = POOLED_SESSION_LABEL
                pooled = True

            for phase in phases:
                speed_rank = None
                if speed_reindex:
                    for name in (f"speed_rank_table_{phase}.csv", "speed_rank_table.csv"):
                        rank_path = rank_root / name
                        if rank_path.is_file():
                            speed_rank = load_speed_rank_table(rank_path)
                            break
                limits = model_plot_limits(global_occ, speed_rank=speed_rank)

                trial_series: list[np.ndarray] = []
                for animal_id, member_session, trial in members:
                    tkey = f"{animal_id}-{member_session}-{trial}"
                    manifest = all_manifests.get(tkey)
                    if manifest is None:
                        continue
                    if tkey not in results:
                        continue
                    syll = np.asarray(results[tkey]["syllable"]).ravel()
                    mv = movement_series_for_trial(
                        manifest,
                        stream,  # type: ignore[arg-type]
                        legacy_db,
                        pre_cfg=pre_cfg,
                    )
                    if mv is None or mv.source_frames.shape[0] != syll.shape[0]:
                        continue
                    xy = load_ambulation_xy(legacy_db, manifest)
                    if xy is None:
                        continue
                    fps = _trial_fps(h5, animal_id, member_session, trial)
                    fts = _frame_to_state(xy)
                    series = trial_phase_syllable_by_bin(
                        syll,
                        mv.source_frames,
                        fts,
                        phase=phase,
                        fps=fps,
                    )
                    if series is not None:
                        trial_series.append(series)

                agg = aggregate_trial_bins(trial_series, global_occ, limits.stack_order)
                if agg is None or agg.n_trials.max() == 0:
                    continue

                rel = _export_relpath_ethogram(session, tx, strain, sex, block, phase, pooled=pooled)
                out_path = out_dir / rel
                title = (
                    f"{stream}/seed_{seed}  {session}  {tx}/{strain}/{sex}  "
                    f"block {block}  {phase.upper()}  n≤{int(agg.n_trials.max())}"
                )
                render_block_ethogram(agg, limits=limits, title=title, out_path=out_path)

                summary_rows.append(
                    {
                        "stream": stream,
                        "seed": seed,
                        "phase": phase,
                        "session": session,
                        "tx": tx,
                        "sex": sex,
                        "strain": strain,
                        "block": block,
                        "block_trials": ",".join(ALL_TRIAL_BLOCKS[block]),
                        "n_trials": len(trial_series),
                        "max_phase_seconds": round(agg.max_bins * BIN_SECONDS, 3),
                        "output_path": str(out_path.resolve()),
                    }
                )

    summary_path = out_dir / "summary.csv"
    write_header = not summary_path.is_file()
    with summary_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(summary_rows)

    return summary_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kpms-root", type=Path, default=None)
    parser.add_argument("--legacy-db", type=Path, default=None)
    parser.add_argument("--manifest-path", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--tracking-h5", type=Path, default=None)
    parser.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="e.g. anatomical/seed_042 (default: all 15)",
    )
    parser.add_argument(
        "--phases",
        nargs="*",
        choices=("run", "iti"),
        default=("run", "iti"),
    )
    parser.add_argument("--blocks", default=None)
    parser.add_argument("--sessions", default=None)
    parser.add_argument("--no-full-session", action="store_true")
    parser.add_argument("--no-all-sessions", action="store_true")
    parser.add_argument(
        "--legend-only",
        action="store_true",
        help="Write DATA_DICTIONARY.md and legend.png only (no PNG sweep)",
    )
    parser.add_argument(
        "--speed-reindex",
        action="store_true",
        help="Color/stack by speed_rank_table.csv from model dir (from syllable_speed_cluster.py)",
    )
    args = parser.parse_args()

    out_root = args.out_dir.expanduser().resolve()
    md_path, legend_path = write_global_artifacts(out_root)
    print(f"Wrote {md_path}")
    print(f"Wrote {legend_path}")
    if args.legend_only:
        return 0

    missing = [
        name
        for name, val in (
            ("--kpms-root", args.kpms_root),
            ("--legacy-db", args.legacy_db),
            ("--manifest-path", args.manifest_path),
        )
        if val is None
    ]
    if missing:
        parser.error(f"required when not using --legend-only: {', '.join(missing)}")

    kpms_root = args.kpms_root.expanduser().resolve()
    legacy_db = args.legacy_db.expanduser().resolve()
    manifest_path = args.manifest_path.expanduser().resolve()
    models = _parse_models(args.models)
    blocks = _parse_blocks(args.blocks, valid=TRIAL_BLOCKS)
    sessions = _parse_sessions(args.sessions)
    phases: tuple[PhaseKind, ...] = tuple(args.phases)  # type: ignore[assignment]

    if models:
        stream0, seed0 = models[0]
        results0 = kpms_root / stream0 / f"seed_{seed0}" / "results_apply.h5"
        if results0.is_file():
            limits0 = model_plot_limits(build_global_occupancy(results0))
            write_global_artifacts(out_root, limits=limits0)
            print(f"Refreshed legend using {stream0}/seed_{seed0} limits")

    total = 0
    for stream, seed in models:
        model_out = args.out_dir.expanduser().resolve() / stream / f"seed_{seed}"
        results_path = kpms_root / stream / f"seed_{seed}" / "results_apply.h5"
        if results_path.is_file():
            model_limits = model_plot_limits(build_global_occupancy(results_path))
            model_legend = render_global_legend(
                model_out / LEGEND_FILENAME,
                limits=model_limits,
                model_label=f"{stream}/seed_{seed}",
            )
            print(f"Wrote {model_legend}")

        rows = run_block_ethogram_exports(
            kpms_root=kpms_root,
            legacy_db=legacy_db,
            manifest_path=manifest_path,
            out_dir=model_out,
            stream=stream,
            seed=seed,
            phases=phases,
            sessions=sessions,
            blocks=blocks,
            group_by_session=True,
            speed_reindex=args.speed_reindex,
            speed_rank_dir=model_out,
        )
        total += len(rows)
        print(f"{stream}/seed_{seed}: {len(rows)} PNGs -> {model_out}")

        if not args.no_full_session:
            full_out = model_out / "trial1-9"
            rows = run_block_ethogram_exports(
                kpms_root=kpms_root,
                legacy_db=legacy_db,
                manifest_path=manifest_path,
                out_dir=full_out,
                stream=stream,
                seed=seed,
                phases=phases,
                sessions=sessions,
                blocks=(FULL_SESSION_BLOCK,),
                group_by_session=True,
                speed_reindex=args.speed_reindex,
                speed_rank_dir=model_out,
            )
            total += len(rows)
            print(f"  trial1-9: {len(rows)} PNGs")

        if not args.no_all_sessions:
            pooled_out = model_out / "all-sessions"
            rows = run_block_ethogram_exports(
                kpms_root=kpms_root,
                legacy_db=legacy_db,
                manifest_path=manifest_path,
                out_dir=pooled_out,
                stream=stream,
                seed=seed,
                phases=phases,
                sessions=sessions,
                blocks=blocks,
                group_by_session=False,
                speed_reindex=args.speed_reindex,
                speed_rank_dir=model_out,
            )
            total += len(rows)
            if not args.no_full_session:
                rows = run_block_ethogram_exports(
                    kpms_root=kpms_root,
                    legacy_db=legacy_db,
                    manifest_path=manifest_path,
                    out_dir=pooled_out / "trial1-9",
                    stream=stream,
                    seed=seed,
                    phases=phases,
                    sessions=sessions,
                    blocks=(FULL_SESSION_BLOCK,),
                    group_by_session=False,
                    speed_reindex=args.speed_reindex,
                    speed_rank_dir=model_out,
                )
                total += len(rows)
            print("  all-sessions: done")

    print(f"Total PNGs written: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
