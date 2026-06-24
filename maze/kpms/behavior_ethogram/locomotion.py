"""Locomotion tier rules on behavior-token centroids (Stage III)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

DEFAULT_LOCOMOTION_RULES: dict[str, Any] = {
    "version": "v1",
    "fallback_tier": "slow_explore",
    "rules": [
        {
            "tier": "still",
            "priority": 0,
            "max_mean_speed_mps": 0.08,
            "max_mean_abs_dheading": 0.35,
        },
        {
            "tier": "fast_transit",
            "priority": 1,
            "min_mean_speed_mps": 0.18,
            "max_mean_abs_dheading": 0.35,
        },
        {
            "tier": "turn_heavy",
            "priority": 2,
            "min_mean_abs_dheading": 0.35,
        },
        {
            "tier": "slow_explore",
            "priority": 3,
        },
    ],
}

LOCO_TIER_COLORS_BGR: dict[str, tuple[int, int, int]] = {
    "still": (180, 180, 180),
    "slow_explore": (80, 200, 80),
    "fast_transit": (60, 120, 255),
    "turn_heavy": (200, 120, 60),
    "ambiguous": (80, 80, 200),
    "unknown": (40, 40, 40),
}


@dataclass(frozen=True)
class TokenCentroid:
    behavior_token: int
    mean_speed_mps: float
    mean_abs_dheading: float
    n_bouts: int


@dataclass(frozen=True)
class BoutTokenRow:
    seed: str
    trial_key: str
    bout_index: int
    behavior_token: int
    bout_mean_speed_mps: float
    bout_mean_abs_dheading: float
    ambiguous: bool
    tier: str


def load_locomotion_rules_yaml(path: Path | str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        raise ValueError(f"locomotion rules must be a mapping: {path}")
    return doc


def write_locomotion_rules_yaml(path: Path | str, doc: Mapping[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(dict(doc), f, sort_keys=False)


def rule_matches(
    *,
    mean_speed_mps: float,
    mean_abs_dheading: float,
    rule: Mapping[str, Any],
) -> bool:
    if "min_mean_speed_mps" in rule and mean_speed_mps < float(rule["min_mean_speed_mps"]):
        return False
    if "max_mean_speed_mps" in rule and mean_speed_mps > float(rule["max_mean_speed_mps"]):
        return False
    if "min_mean_abs_dheading" in rule and mean_abs_dheading < float(rule["min_mean_abs_dheading"]):
        return False
    if "max_mean_abs_dheading" in rule and mean_abs_dheading > float(rule["max_mean_abs_dheading"]):
        return False
    return True


def assign_tier_from_scalars(
    *,
    mean_speed_mps: float,
    mean_abs_dheading: float,
    rules_doc: Mapping[str, Any],
) -> str:
    rules = sorted(
        rules_doc.get("rules", []),
        key=lambda r: int(r.get("priority", 999)),
    )
    for rule in rules:
        if rule_matches(
            mean_speed_mps=mean_speed_mps,
            mean_abs_dheading=mean_abs_dheading,
            rule=rule,
        ):
            return str(rule["tier"])
    return str(rules_doc.get("fallback_tier", "slow_explore"))


def compute_token_centroids(rows: Sequence[BoutTokenRow]) -> dict[int, TokenCentroid]:
    by_token: dict[int, list[BoutTokenRow]] = {}
    for row in rows:
        if row.ambiguous:
            continue
        by_token.setdefault(int(row.behavior_token), []).append(row)
    out: dict[int, TokenCentroid] = {}
    for token, group in by_token.items():
        speeds = [r.bout_mean_speed_mps for r in group]
        dheads = [r.bout_mean_abs_dheading for r in group]
        out[token] = TokenCentroid(
            behavior_token=token,
            mean_speed_mps=float(sum(speeds) / len(speeds)),
            mean_abs_dheading=float(sum(dheads) / len(dheads)),
            n_bouts=len(group),
        )
    return out


def tier_by_token_from_centroids(
    centroids: Mapping[int, TokenCentroid],
    rules_doc: Mapping[str, Any],
) -> dict[int, str]:
    return {
        token: assign_tier_from_scalars(
            mean_speed_mps=c.mean_speed_mps,
            mean_abs_dheading=c.mean_abs_dheading,
            rules_doc=rules_doc,
        )
        for token, c in centroids.items()
    }


def assign_bout_tiers(
    rows: Sequence[BoutTokenRow],
    tier_by_token: Mapping[int, str],
) -> list[BoutTokenRow]:
    out: list[BoutTokenRow] = []
    for row in rows:
        if row.ambiguous:
            tier = "ambiguous"
        else:
            tier = tier_by_token.get(int(row.behavior_token), "unknown")
        out.append(
            BoutTokenRow(
                seed=row.seed,
                trial_key=row.trial_key,
                bout_index=row.bout_index,
                behavior_token=row.behavior_token,
                bout_mean_speed_mps=row.bout_mean_speed_mps,
                bout_mean_abs_dheading=row.bout_mean_abs_dheading,
                ambiguous=row.ambiguous,
                tier=tier,
            )
        )
    return out


TOKEN_TIER_FIELDS = (
    "seed",
    "trial_key",
    "bout_index",
    "behavior_token",
    "bout_mean_speed_mps",
    "bout_mean_abs_dheading",
    "ambiguous",
    "tier",
    "token_mean_speed_mps",
    "token_mean_abs_dheading",
    "token_n_bouts",
)


def write_token_tiers_csv(path: Path | str, rows: Sequence[BoutTokenRow], centroids: Mapping[int, TokenCentroid]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(TOKEN_TIER_FIELDS))
        writer.writeheader()
        for row in rows:
            c = centroids.get(int(row.behavior_token))
            writer.writerow(
                {
                    "seed": row.seed,
                    "trial_key": row.trial_key,
                    "bout_index": row.bout_index,
                    "behavior_token": row.behavior_token,
                    "bout_mean_speed_mps": row.bout_mean_speed_mps,
                    "bout_mean_abs_dheading": row.bout_mean_abs_dheading,
                    "ambiguous": int(row.ambiguous),
                    "tier": row.tier,
                    "token_mean_speed_mps": "" if c is None else c.mean_speed_mps,
                    "token_mean_abs_dheading": "" if c is None else c.mean_abs_dheading,
                    "token_n_bouts": "" if c is None else c.n_bouts,
                }
            )


def tier_color_bgr(tier: str) -> tuple[int, int, int]:
    return LOCO_TIER_COLORS_BGR.get(str(tier), LOCO_TIER_COLORS_BGR["unknown"])
