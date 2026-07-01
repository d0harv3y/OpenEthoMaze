"""Map producer labels to harness anchor buckets (moving / still / ignore)."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from .grammar_contract import OVERLAY_SPEED_GRAY_HI_MPS, OVERLAY_SPEED_GRAY_LO_MPS
from .locomotion import (
    DEFAULT_LOCOMOTION_RULES,
    BoutTokenRow,
    compute_token_centroids,
    tier_by_token_from_centroids,
)


def behavior_name_from_pattern(pattern: Sequence[int]) -> str:
    """Synthetic portable name for an uncured syllable n-gram."""
    slug = "_".join(str(int(x)) for x in pattern)
    return f"pat_{slug}"


def infer_anchor_bucket_from_mean_speed(
    mean_speed_mps: float,
    *,
    still_max_mps: float = OVERLAY_SPEED_GRAY_LO_MPS,
    moving_min_mps: float = OVERLAY_SPEED_GRAY_HI_MPS,
) -> str:
    """Classify pooled bout speed into harness buckets (gray zone → ignore)."""
    if not math.isfinite(mean_speed_mps):
        return "ignore"
    if mean_speed_mps <= float(still_max_mps):
        return "still"
    if mean_speed_mps >= float(moving_min_mps):
        return "moving"
    return "ignore"


def anchor_bucket_from_locomotion_tier(tier: str) -> str:
    """Map Stage III locomotion tier to harness anchor bucket."""
    t = str(tier).strip().lower()
    if t == "still":
        return "still"
    if t in {"fast_transit", "slow_explore", "turn_heavy"}:
        return "moving"
    return "ignore"


def token_anchor_buckets_from_bout_rows(
    rows: Sequence[BoutTokenRow],
    *,
    rules_doc: Mapping[str, object] | None = None,
) -> dict[int, str]:
    """Infer ``behavior_token`` → anchor bucket from token speed/heading centroids."""
    doc = dict(DEFAULT_LOCOMOTION_RULES if rules_doc is None else rules_doc)
    centroids = compute_token_centroids(rows)
    tier_by_token = tier_by_token_from_centroids(centroids, doc)
    return {
        int(token): anchor_bucket_from_locomotion_tier(tier)
        for token, tier in tier_by_token.items()
    }


def bout_token_rows_from_table(
    table: Sequence[Mapping[str, str]],
    *,
    seed: str | None = None,
) -> list[BoutTokenRow]:
    """Build :class:`BoutTokenRow` list from ``bout_behavior_tokens.csv`` rows."""
    out: list[BoutTokenRow] = []
    for row in table:
        if seed is not None and str(row.get("seed", "")) != str(seed):
            continue
        token_raw = str(row.get("behavior_token", "")).strip()
        if not token_raw:
            continue
        out.append(
            BoutTokenRow(
                seed=str(row["seed"]),
                trial_key=str(row["trial_key"]),
                bout_index=int(row["bout_index"]),
                behavior_token=int(token_raw),
                bout_mean_speed_mps=float(row["bout_mean_speed_mps"]),
                bout_mean_abs_dheading=float(row["bout_mean_abs_dheading"]),
                ambiguous=bool(int(row.get("ambiguous", "0"))),
                tier="",
            )
        )
    return out
