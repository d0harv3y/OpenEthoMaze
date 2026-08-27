"""Phase II locomotion tier helpers (scratch).

YAML rule assignment on anatomical token centroids; testable without H5/GPU.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from behavior_ethogram_phase_i import (
    _parse_boolish,
    _parse_float,
    _phase_suffix,
    hdbscan_labels_path,
)

LOCOMOTION_TIERS = ("still", "slow_explore", "fast_transit", "turn_heavy", "ambiguous")

DEFAULT_LOCOMOTION_RULES: dict[str, Any] = {
    "version": "v1",
    "description": (
        "Hand-tuned locomotion tiers on anatomical token centroids (ADR 0005). "
        "Review calibration histograms before replacing thresholds."
    ),
    "fallback_tier": "slow_explore",
    "rules": [
        {
            "tier": "turn_heavy",
            "mean_abs_dheading_gte": 0.35,
            "mean_speed_mps_gte": 0.04,
            "mean_speed_mps_lt": 0.25,
        },
        {
            "tier": "fast_transit",
            "mean_speed_mps_gte": 0.20,
            "mean_abs_dheading_lt": 0.25,
        },
        {
            "tier": "still",
            "mean_speed_mps_lt": 0.05,
            "mean_abs_dheading_lt": 0.15,
        },
        {
            "tier": "slow_explore",
            "mean_speed_mps_gte": 0.05,
            "mean_speed_mps_lt": 0.20,
        },
    ],
}

TOKEN_TIERS_FIELDS = (
    "seed",
    "raw_syllable_id",
    "cluster_id",
    "tier",
    "ambiguous",
    "mean_speed_mps",
    "mean_abs_dheading",
    "frac_still",
    "bout_speed_iqr",
    "token_mean_speed_mps",
    "token_mean_abs_dheading",
)


def default_phase_ii_out_dir(kpms_root: Path) -> Path:
    return kpms_root / "behavior_ethogram" / "phase_ii"


def locomotion_tiers_yaml_path(phase_ii_dir: Path) -> Path:
    return phase_ii_dir / "locomotion_tiers.yaml"


def token_tiers_csv_path(phase_ii_dir: Path, *, phase: str = "all") -> Path:
    return phase_ii_dir / f"token_tiers{_phase_suffix(phase)}.csv"


def calibration_dir(phase_ii_dir: Path) -> Path:
    return phase_ii_dir / "calibration"


def calibration_summary_path(phase_ii_dir: Path, *, phase: str = "all") -> Path:
    return calibration_dir(phase_ii_dir) / f"summary{_phase_suffix(phase)}.json"


@dataclass(frozen=True)
class PrototypeLabelRow:
    seed: str
    raw_syllable_id: int
    cluster_id: int
    mean_speed_mps: float
    mean_abs_dheading: float
    frac_still: float
    bout_speed_iqr: float
    ambiguous: bool


@dataclass(frozen=True)
class TokenCentroid:
    cluster_id: int
    mean_speed_mps: float
    mean_abs_dheading: float
    n_prototypes: int


def load_prototype_label_rows(path: Path) -> list[PrototypeLabelRow]:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows: list[PrototypeLabelRow] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(
                PrototypeLabelRow(
                    seed=str(row["seed"]).zfill(3),
                    raw_syllable_id=int(row["raw_syllable_id"]),
                    cluster_id=int(row.get("cluster_id", -1)),
                    mean_speed_mps=_parse_float(row.get("mean_speed_mps")),
                    mean_abs_dheading=_parse_float(row.get("mean_abs_dheading")),
                    frac_still=_parse_float(row.get("frac_still")),
                    bout_speed_iqr=_parse_float(row.get("bout_speed_iqr")),
                    ambiguous=_parse_boolish(row.get("ambiguous")),
                )
            )
    return rows


def rule_matches(
    *,
    mean_speed_mps: float,
    mean_abs_dheading: float,
    rule: Mapping[str, Any],
) -> bool:
    if "mean_speed_mps_gte" in rule and mean_speed_mps < float(rule["mean_speed_mps_gte"]):
        return False
    if "mean_speed_mps_lt" in rule and mean_speed_mps >= float(rule["mean_speed_mps_lt"]):
        return False
    if "mean_abs_dheading_gte" in rule and mean_abs_dheading < float(rule["mean_abs_dheading_gte"]):
        return False
    if "mean_abs_dheading_lt" in rule and mean_abs_dheading >= float(rule["mean_abs_dheading_lt"]):
        return False
    return True


def assign_tier_from_scalars(
    *,
    mean_speed_mps: float,
    mean_abs_dheading: float,
    rules_doc: Mapping[str, Any],
) -> str:
    for rule in rules_doc.get("rules", []):
        if rule_matches(
            mean_speed_mps=mean_speed_mps,
            mean_abs_dheading=mean_abs_dheading,
            rule=rule,
        ):
            return str(rule["tier"])
    return str(rules_doc.get("fallback_tier", "slow_explore"))


def compute_token_centroids(
    prototypes: Sequence[PrototypeLabelRow],
    *,
    include_ambiguous: bool = False,
) -> dict[int, TokenCentroid]:
    buckets: dict[int, list[PrototypeLabelRow]] = defaultdict(list)
    for row in prototypes:
        if row.cluster_id < 0:
            continue
        if row.ambiguous and not include_ambiguous:
            continue
        buckets[row.cluster_id].append(row)
    out: dict[int, TokenCentroid] = {}
    for cluster_id, members in buckets.items():
        speeds = [m.mean_speed_mps for m in members]
        dhs = [m.mean_abs_dheading for m in members]
        out[cluster_id] = TokenCentroid(
            cluster_id=cluster_id,
            mean_speed_mps=float(np.mean(speeds)),
            mean_abs_dheading=float(np.mean(dhs)),
            n_prototypes=len(members),
        )
    return out


def assign_tiers_by_cluster(
    centroids: Mapping[int, TokenCentroid],
    rules_doc: Mapping[str, Any],
) -> dict[int, str]:
    return {
        cluster_id: assign_tier_from_scalars(
            mean_speed_mps=centroid.mean_speed_mps,
            mean_abs_dheading=centroid.mean_abs_dheading,
            rules_doc=rules_doc,
        )
        for cluster_id, centroid in centroids.items()
    }


def build_token_tier_rows(
    prototypes: Sequence[PrototypeLabelRow],
    tier_by_cluster: Mapping[int, str],
    centroids: Mapping[int, TokenCentroid],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for proto in sorted(prototypes, key=lambda p: (p.seed, p.raw_syllable_id)):
        if proto.ambiguous or proto.cluster_id < 0:
            tier = "ambiguous"
            token_speed = ""
            token_dh = ""
        else:
            tier = tier_by_cluster[proto.cluster_id]
            centroid = centroids[proto.cluster_id]
            token_speed = round(centroid.mean_speed_mps, 6)
            token_dh = round(centroid.mean_abs_dheading, 6)
        rows.append(
            {
                "seed": proto.seed,
                "raw_syllable_id": proto.raw_syllable_id,
                "cluster_id": proto.cluster_id,
                "tier": tier,
                "ambiguous": int(proto.ambiguous),
                "mean_speed_mps": round(proto.mean_speed_mps, 6),
                "mean_abs_dheading": round(proto.mean_abs_dheading, 6),
                "frac_still": round(proto.frac_still, 6),
                "bout_speed_iqr": round(proto.bout_speed_iqr, 6),
                "token_mean_speed_mps": token_speed,
                "token_mean_abs_dheading": token_dh,
            }
        )
    return rows


def calibration_scalar_summary(
    prototypes: Sequence[PrototypeLabelRow],
) -> dict[str, object]:
    """Percentile summary for histogram review (ADR 0005 gate)."""
    eligible = [p for p in prototypes if not p.ambiguous and p.cluster_id >= 0]
    speeds = np.asarray([p.mean_speed_mps for p in eligible], dtype=np.float64)
    dhs = np.asarray([p.mean_abs_dheading for p in eligible], dtype=np.float64)
    if speeds.size == 0:
        return {"n_prototypes": 0, "n_tokens": 0}
    percentiles = (5, 25, 50, 75, 95)
    return {
        "n_prototypes": len(eligible),
        "n_tokens": len({p.cluster_id for p in eligible}),
        "mean_speed_mps": {
            f"p{p}": float(v) for p, v in zip(percentiles, np.percentile(speeds, percentiles), strict=True)
        },
        "mean_abs_dheading": {
            f"p{p}": float(v) for p, v in zip(percentiles, np.percentile(dhs, percentiles), strict=True)
        },
    }


def load_locomotion_rules_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        raise ValueError(f"Expected mapping in {path}")
    return doc


def write_locomotion_rules_yaml(path: Path, rules_doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(dict(rules_doc), fh, sort_keys=False, default_flow_style=False)


def write_token_tiers_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TOKEN_TIERS_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_calibration_summary(path: Path, summary: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def calibrate_from_phase_i(
    phase_i_dir: Path,
    *,
    phase: str = "all",
    rules_doc: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, object]], dict[int, TokenCentroid], dict[int, str], dict[str, object]]:
    rules = dict(rules_doc or DEFAULT_LOCOMOTION_RULES)
    prototypes = load_prototype_label_rows(
        hdbscan_labels_path(phase_i_dir, "anatomical", phase=phase),
    )
    centroids = compute_token_centroids(prototypes)
    tier_by_cluster = assign_tiers_by_cluster(centroids, rules)
    token_rows = build_token_tier_rows(prototypes, tier_by_cluster, centroids)
    summary = calibration_scalar_summary(prototypes)
    summary["tier_counts"] = {
        tier: sum(1 for row in token_rows if row["tier"] == tier) for tier in LOCOMOTION_TIERS
    }
    return token_rows, centroids, tier_by_cluster, summary


def render_calibration_plots(
    out_dir: Path,
    prototypes: Sequence[PrototypeLabelRow],
    token_rows: Sequence[Mapping[str, object]],
) -> list[Path]:
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    tier_by_key = {
        (str(row["seed"]), int(row["raw_syllable_id"])): str(row["tier"]) for row in token_rows
    }
    eligible = [p for p in prototypes if not p.ambiguous and p.cluster_id >= 0]
    if not eligible:
        return []

    speeds = np.array([p.mean_speed_mps for p in eligible])
    dhs = np.array([p.mean_abs_dheading for p in eligible])
    tiers = [tier_by_key[(p.seed, p.raw_syllable_id)] for p in eligible]
    colors = {
        "still": "#4C72B0",
        "slow_explore": "#55A868",
        "fast_transit": "#C44E52",
        "turn_heavy": "#8172B3",
        "ambiguous": "#CCB974",
    }

    written: list[Path] = []

    fig, ax = plt.subplots(figsize=(6, 5))
    for tier in LOCOMOTION_TIERS:
        mask = [t == tier for t in tiers]
        if not any(mask):
            continue
        ax.scatter(
            speeds[mask],
            dhs[mask],
            s=18,
            alpha=0.75,
            label=tier,
            c=colors.get(tier, "#333333"),
        )
    ax.set_xlabel("mean_speed_mps (prototype)")
    ax.set_ylabel("mean_abs_dheading (prototype)")
    ax.set_title("Anatomical prototypes by locomotion tier")
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    scatter_path = out_dir / "tier_scatter_prototypes.png"
    fig.savefig(scatter_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    written.append(scatter_path)

    for name, values in (("mean_speed_mps", speeds), ("mean_abs_dheading", dhs)):
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.hist(values, bins=min(30, max(5, values.size // 3))*2, color="#4C72B0", alpha=0.85)
        ax.set_xlabel(name)
        ax.set_ylabel("prototype count")
        ax.set_title(f"Histogram: {name}")
        fig.tight_layout()
        hist_path = out_dir / f"hist_{name}.png"
        fig.savefig(hist_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        written.append(hist_path)

    return written
