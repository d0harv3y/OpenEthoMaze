"""Phase I behavioral ethogram pure helpers (scratch).

Testable kinematic scalar aggregation, bout QC, and CLI job parsing without H5/GPU.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import numpy as np

STREAMS = ("anatomical", "blob", "fused")
SEEDS = ("005", "013", "042", "067", "111")

# Conservative default until histogram calibration (ADR 0007 / 0005).
DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS = 0.12
DEFAULT_LOW_CONTRAST_MPS = 0.03

PrototypeKey = tuple[str, int]

CONTRAST_SIDECAR_FIELDS = (
    "seed",
    "raw_syllable_id",
    "cluster_id",
    "ambiguous_anatomical",
    "mean_speed_mps_anatomical",
    "mean_speed_mps_blob",
    "mean_speed_mps_fused",
    "frac_still_anatomical",
    "frac_still_blob",
    "frac_still_fused",
    "delta_speed_ab",
    "delta_speed_af",
    "delta_frac_still_ab",
    "blob_present",
    "fused_present",
    "fused_validates_ab",
)

K = TypeVar("K")


def default_phase_i_out_dir(kpms_root: Path) -> Path:
    """ADR 0009 cohort artifact root for Phase I token tables."""
    return kpms_root / "behavior_ethogram" / "phase_i"


def _phase_suffix(phase: str) -> str:
    return "" if phase == "all" else f"_{phase}"


def hdbscan_labels_path(phase_i_dir: Path, stream: str, *, phase: str = "all") -> Path:
    return phase_i_dir / stream / "shared" / f"hdbscan_labels{_phase_suffix(phase)}.csv"


def contrast_sidecar_path(phase_i_dir: Path, *, phase: str = "all") -> Path:
    return phase_i_dir / f"contrast_sidecar{_phase_suffix(phase)}.csv"


@dataclass(frozen=True)
class StreamPrototypeScalars:
    mean_speed_mps: float
    frac_still: float
    cluster_id: int = -1
    ambiguous: bool = False


def _parse_boolish(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes"}


def _parse_float(value: object) -> float:
    if value is None or value == "":
        return float("nan")
    return float(value)


def load_hdbscan_label_table(path: Path) -> dict[PrototypeKey, StreamPrototypeScalars]:
    """Load per-prototype scalars keyed by ``(seed, raw_syllable_id)``."""
    if not path.is_file():
        raise FileNotFoundError(path)
    out: dict[PrototypeKey, StreamPrototypeScalars] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (str(row["seed"]).zfill(3), int(row["raw_syllable_id"]))
            out[key] = StreamPrototypeScalars(
                mean_speed_mps=_parse_float(row.get("mean_speed_mps")),
                frac_still=_parse_float(row.get("frac_still")),
                cluster_id=int(row.get("cluster_id", -1)),
                ambiguous=_parse_boolish(row.get("ambiguous")),
            )
    return out


def fused_validates_ab(
    mean_speed_anatomical: float,
    mean_speed_blob: float,
    mean_speed_fused: float,
    *,
    low_contrast_mps: float = DEFAULT_LOW_CONTRAST_MPS,
) -> bool:
    """True when fused speed supports the anatomical–blob contrast (ADR 0004)."""
    if not all(map(np.isfinite, (mean_speed_anatomical, mean_speed_blob, mean_speed_fused))):
        return False
    delta_ab = mean_speed_anatomical - mean_speed_blob
    delta_af = mean_speed_anatomical - mean_speed_fused
    if abs(delta_ab) <= low_contrast_mps:
        return abs(delta_af) <= low_contrast_mps
    lo, hi = sorted((mean_speed_blob, mean_speed_anatomical))
    if lo <= mean_speed_fused <= hi:
        return True
    return bool(np.sign(delta_ab) == np.sign(delta_af))


def build_contrast_sidecar_rows(
    anatomical: Mapping[PrototypeKey, StreamPrototypeScalars],
    blob: Mapping[PrototypeKey, StreamPrototypeScalars],
    fused: Mapping[PrototypeKey, StreamPrototypeScalars],
    *,
    low_contrast_mps: float = DEFAULT_LOW_CONTRAST_MPS,
) -> list[dict[str, object]]:
    """Join anatomical-primary prototypes with blob/fused scalars (ADR 0003)."""
    rows: list[dict[str, object]] = []
    for key in sorted(anatomical.keys(), key=lambda k: (k[0], k[1])):
        seed, raw_id = key
        a = anatomical[key]
        b = blob.get(key)
        f = fused.get(key)
        speed_a = a.mean_speed_mps
        speed_b = b.mean_speed_mps if b is not None else float("nan")
        speed_f = f.mean_speed_mps if f is not None else float("nan")
        frac_a = a.frac_still
        frac_b = b.frac_still if b is not None else float("nan")
        frac_f = f.frac_still if f is not None else float("nan")
        blob_present = b is not None
        fused_present = f is not None
        delta_ab = speed_a - speed_b if blob_present else float("nan")
        delta_af = speed_a - speed_f if fused_present else float("nan")
        delta_frac_ab = frac_a - frac_b if blob_present else float("nan")
        validates = (
            fused_validates_ab(speed_a, speed_b, speed_f, low_contrast_mps=low_contrast_mps)
            if blob_present and fused_present
            else False
        )
        rows.append(
            {
                "seed": seed,
                "raw_syllable_id": raw_id,
                "cluster_id": a.cluster_id,
                "ambiguous_anatomical": int(a.ambiguous),
                "mean_speed_mps_anatomical": round(speed_a, 6),
                "mean_speed_mps_blob": round(speed_b, 6) if blob_present else "",
                "mean_speed_mps_fused": round(speed_f, 6) if fused_present else "",
                "frac_still_anatomical": round(frac_a, 6),
                "frac_still_blob": round(frac_b, 6) if blob_present else "",
                "frac_still_fused": round(frac_f, 6) if fused_present else "",
                "delta_speed_ab": round(delta_ab, 6) if blob_present else "",
                "delta_speed_af": round(delta_af, 6) if fused_present else "",
                "delta_frac_still_ab": round(delta_frac_ab, 6) if blob_present else "",
                "blob_present": int(blob_present),
                "fused_present": int(fused_present),
                "fused_validates_ab": int(validates),
            }
        )
    return rows


def write_contrast_sidecar_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CONTRAST_SIDECAR_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def build_contrast_sidecar_from_dirs(
    phase_i_dir: Path,
    *,
    phase: str = "all",
    low_contrast_mps: float = DEFAULT_LOW_CONTRAST_MPS,
) -> list[dict[str, object]]:
    anatomical = load_hdbscan_label_table(hdbscan_labels_path(phase_i_dir, "anatomical", phase=phase))
    blob = load_hdbscan_label_table(hdbscan_labels_path(phase_i_dir, "blob", phase=phase))
    fused = load_hdbscan_label_table(hdbscan_labels_path(phase_i_dir, "fused", phase=phase))
    return build_contrast_sidecar_rows(
        anatomical,
        blob,
        fused,
        low_contrast_mps=low_contrast_mps,
    )


def extend_features_tmax(
    feat: np.ndarray,
    *,
    t_s: int,
    t_max_from: int,
    t_max_to: int,
) -> np.ndarray:
    if t_max_to <= t_max_from:
        return feat[: 3 * t_max_to].copy()
    out = np.zeros(3 * t_max_to, dtype=np.float64)
    out[: 3 * t_max_from] = feat[: 3 * t_max_from]
    for ch in range(3):
        base = feat[ch * t_max_from : ch * t_max_from + t_s]
        fill = float(np.mean(base)) if base.size else 0.0
        out[ch * t_max_to + t_max_from : (ch + 1) * t_max_to] = fill
    return out


def frac_still(is_moving: np.ndarray) -> float:
    """Fraction of frames classified as not moving (legacy ambulation flag)."""
    flags = np.asarray(is_moving, dtype=bool)
    if flags.size == 0:
        return 0.0
    return float(np.mean(~flags))


def mean_abs_dheading(heading: np.ndarray) -> float:
    """Mean absolute consecutive heading change in radians."""
    h = np.asarray(heading, dtype=np.float64)
    if h.size < 2:
        return 0.0
    dh = np.abs(np.diff(np.unwrap(h)))
    return float(np.mean(dh))


def bout_speed_iqr(bout_mean_speeds: Sequence[float]) -> float:
    """IQR of per-bout mean speeds for one syllable prototype."""
    arr = np.asarray(bout_mean_speeds, dtype=np.float64)
    if arr.size < 2:
        return 0.0
    q75, q25 = np.percentile(arr, [75, 25])
    return float(q75 - q25)


def prototype_ambiguous(
    bout_speed_iqr_value: float,
    *,
    threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
) -> bool:
    return bout_speed_iqr_value > threshold_mps


@dataclass(frozen=True)
class PrototypeScalars:
    frac_still: float
    mean_abs_dheading: float
    bout_speed_iqr: float
    ambiguous: bool


def prototype_scalars_from_bouts(
    *,
    is_moving_frames: np.ndarray,
    heading_frames: np.ndarray,
    bout_mean_speeds: Sequence[float],
    ambiguous_threshold_mps: float = DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
) -> PrototypeScalars:
    iqr = bout_speed_iqr(bout_mean_speeds)
    return PrototypeScalars(
        frac_still=frac_still(is_moving_frames),
        mean_abs_dheading=mean_abs_dheading(heading_frames),
        bout_speed_iqr=iqr,
        ambiguous=prototype_ambiguous(iqr, threshold_mps=ambiguous_threshold_mps),
    )


def build_speed_rank_table(stats: dict[K, object], *, mean_speed_attr: str = "mean_speed") -> dict[K, int]:
    """Map syllable key -> speed_index (0 = slowest)."""

    def _mean_speed(key: K) -> float:
        return float(getattr(stats[key], mean_speed_attr))

    ordered = sorted(
        stats.keys(),
        key=lambda k: (_mean_speed(k), k[0], k[1]) if isinstance(k, tuple) else (_mean_speed(k), k),
    )
    return {k: i for i, k in enumerate(ordered)}


def parse_stream_jobs(
    raw: list[str] | None,
    *,
    kpms_root: Path | None = None,
) -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    """Parse ``--models`` into (stream, available_seeds, requested_seeds) jobs."""
    if not raw:
        streams = STREAMS
        seed_lists = {s: list(SEEDS) for s in STREAMS}
    else:
        seed_lists: dict[str, list[str]] = {}
        for item in raw:
            token = item.strip()
            if "/" in token:
                stream, seed_part = token.split("/", 1)
                seed = seed_part.replace("seed_", "").zfill(3)
                seed_lists.setdefault(stream, []).append(seed)
            else:
                seed_lists.setdefault(token, list(SEEDS))
        streams = tuple(seed_lists.keys())

    jobs: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for stream in streams:
        if stream not in STREAMS:
            raise ValueError(f"Unknown stream {stream!r}; expected one of {STREAMS}")
        requested = tuple(dict.fromkeys(seed_lists[stream]))
        if kpms_root is not None:
            seeds = resolve_available_seeds(stream, requested, kpms_root)
        else:
            seeds = requested
        if not seeds:
            raise RuntimeError(f"No results_apply.h5 for stream {stream} (requested {requested})")
        jobs.append((stream, seeds, requested))
    return jobs


def resolve_available_seeds(
    stream: str,
    requested: tuple[str, ...],
    kpms_root: Path,
) -> tuple[str, ...]:
    """Keep seeds that have ``results_apply.h5``; log skips."""
    available: list[str] = []
    for seed in requested:
        path = kpms_root / stream / f"seed_{seed}" / "results_apply.h5"
        if path.is_file():
            available.append(seed)
        else:
            print(f"Skipping {stream}/seed_{seed}: missing {path}")
    return tuple(available)
