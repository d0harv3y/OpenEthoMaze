"""Scaffold and merge ``behavior_token_labels.csv`` for Stage III curation."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .anchor_buckets import anchor_bucket_from_locomotion_tier
from .behavior_token_labels_contract import BEHAVIOR_TOKEN_LABEL_FIELDS
from .locomotion import (
    BoutTokenRow,
    assign_tier_from_scalars,
    compute_token_centroids,
    tier_by_token_from_centroids,
)


@dataclass(frozen=True)
class TokenReferenceStats:
    behavior_token: int
    token_n_bouts: int
    token_mean_speed_mps: float
    token_mean_abs_dheading: float
    locomotion_tier: str
    anchor_bucket: str


def _mean(values: Sequence[float]) -> float:
    if not values:
        return float("nan")
    return float(sum(values) / len(values))


def token_reference_stats_by_id(
    rows: Sequence[BoutTokenRow],
    *,
    rules_doc: Mapping[str, Any],
) -> dict[int, TokenReferenceStats]:
    """Pooled per-token reference scalars and auto locomotion tier."""
    by_token: dict[int, list[BoutTokenRow]] = {}
    for row in rows:
        by_token.setdefault(int(row.behavior_token), []).append(row)

    centroids = compute_token_centroids(rows)
    tier_by_token = tier_by_token_from_centroids(centroids, rules_doc)

    out: dict[int, TokenReferenceStats] = {}
    for token, group in by_token.items():
        n_bouts = len(group)
        non_amb = [r for r in group if not r.ambiguous]
        ref_group = non_amb if non_amb else group
        mean_speed = _mean([r.bout_mean_speed_mps for r in ref_group])
        mean_dheading = _mean([r.bout_mean_abs_dheading for r in ref_group])

        if int(token) in centroids:
            tier = tier_by_token[int(token)]
        elif all(r.ambiguous for r in group):
            tier = "ambiguous"
        else:
            tier = assign_tier_from_scalars(
                mean_speed_mps=mean_speed,
                mean_abs_dheading=mean_dheading,
                rules_doc=rules_doc,
            )

        out[int(token)] = TokenReferenceStats(
            behavior_token=int(token),
            token_n_bouts=n_bouts,
            token_mean_speed_mps=mean_speed,
            token_mean_abs_dheading=mean_dheading,
            locomotion_tier=tier,
            anchor_bucket=anchor_bucket_from_locomotion_tier(tier),
        )
    return out


def _reference_row_dict(stats: TokenReferenceStats) -> dict[str, str]:
    return {
        "behavior_token": str(int(stats.behavior_token)),
        "token_n_bouts": str(int(stats.token_n_bouts)),
        "token_mean_speed_mps": f"{stats.token_mean_speed_mps:.6f}",
        "token_mean_abs_dheading": f"{stats.token_mean_abs_dheading:.6f}",
        "locomotion_tier": stats.locomotion_tier,
        "behavior_name": "",
        "anchor_bucket": stats.anchor_bucket,
        "reviewed_at": "",
        "reviewed_trial_key": "",
        "notes": "",
    }


def scaffold_behavior_token_label_rows(
    rows: Sequence[BoutTokenRow],
    *,
    rules_doc: Mapping[str, Any],
    min_token_bouts: int = 1,
) -> list[dict[str, str]]:
    """Build fresh label rows from bout token table (reference columns only)."""
    stats_by_token = token_reference_stats_by_id(rows, rules_doc=rules_doc)
    out: list[dict[str, str]] = []
    for token in sorted(stats_by_token):
        stats = stats_by_token[token]
        if int(stats.token_n_bouts) < int(min_token_bouts):
            continue
        out.append(_reference_row_dict(stats))
    return out


def merge_behavior_token_label_rows(
    scaffolded: Sequence[Mapping[str, str]],
    existing: Sequence[Mapping[str, str]],
    *,
    force: bool = False,
) -> list[dict[str, str]]:
    """Merge scaffold reference columns with prior curation, preserving curated fields."""
    prior = {str(row["behavior_token"]).strip(): dict(row) for row in existing}
    merged: list[dict[str, str]] = []
    for row in scaffolded:
        token = str(row["behavior_token"]).strip()
        base = dict(row)
        old = prior.get(token)
        if old is not None and not force:
            for field in ("behavior_name", "anchor_bucket", "reviewed_at", "reviewed_trial_key", "notes"):
                val = str(old.get(field, "")).strip()
                if val:
                    base[field] = val
        merged.append(base)
    return merged


def write_behavior_token_labels_csv(path: Path | str, rows: Sequence[Mapping[str, str]]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(BEHAVIOR_TOKEN_LABEL_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in BEHAVIOR_TOKEN_LABEL_FIELDS})
    return p


def init_behavior_token_labels(
    *,
    token_rows: Sequence[BoutTokenRow],
    rules_doc: Mapping[str, Any],
    out_csv: Path,
    min_token_bouts: int = 1,
    force: bool = False,
) -> tuple[Path, list[dict[str, str]]]:
    """Scaffold or refresh ``behavior_token_labels.csv``; return path and rows written."""
    scaffolded = scaffold_behavior_token_label_rows(
        token_rows,
        rules_doc=rules_doc,
        min_token_bouts=min_token_bouts,
    )
    if out_csv.is_file() and not force:
        existing = read_behavior_token_labels_csv(out_csv)
        rows = merge_behavior_token_label_rows(scaffolded, existing, force=False)
    else:
        rows = [dict(r) for r in scaffolded]
    write_behavior_token_labels_csv(out_csv, rows)
    return out_csv, rows


def read_behavior_token_labels_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate_ethology_curation_complete(
    label_rows: Sequence[Mapping[str, str]],
    *,
    min_token_bouts: int = 20,
) -> list[str]:
    """Return human-readable errors for tokens failing ethology review gate."""
    errors: list[str] = []
    for row in label_rows:
        n_bouts = int(str(row.get("token_n_bouts", "0")).strip() or "0")
        if n_bouts < int(min_token_bouts):
            continue
        token = str(row.get("behavior_token", "")).strip()
        name = str(row.get("behavior_name", "")).strip()
        reviewed_at = str(row.get("reviewed_at", "")).strip()
        if not name:
            errors.append(f"behavior_token {token}: missing behavior_name (token_n_bouts={n_bouts})")
        elif not reviewed_at:
            errors.append(f"behavior_token {token}: missing reviewed_at (behavior_name={name!r})")
    return errors
