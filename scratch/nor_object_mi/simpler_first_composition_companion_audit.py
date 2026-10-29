"""Audit locked Composition-Companion families against consensus CSVs (no recompute).

Family A: session-step composition / engagement from
``condition_consensus_animal_session_tests_long.csv``.

Family B: Shannon level at ``NOR_REC3hr`` × ``no_obj`` from slides_pack consensus.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402

_ROOT = Path(r"D:\sack\datas\impress\moseq_251017\_nor_object_mi")
SESSION_LONG = _ROOT / "simpler_first_condition_on_paired_delta" / "condition_consensus_animal_session_tests_long.csv"
SHANNON_LEVEL = _ROOT / "slides_pack" / "shannon" / "shannon_level_kruskal.csv"
DEFAULT_OUT = _ROOT / "simpler_first_composition_companion_audit"

# Locked before this audit script (2026-10-05); keys must match consensus rows.
COMPANION_A_KEYS: tuple[dict[str, str], ...] = (
    {
        "grain": "near_0p10",
        "sex": "M",
        "metric": "braycurtis",
        "trial": "nvl_obj",
        "session_step": "condition->REC3hr",
        "weighting": "bout_count",
    },
    {
        "grain": "near_0p10",
        "sex": "M",
        "metric": "braycurtis",
        "trial": "nvl_obj",
        "session_step": "condition->REC3hr",
        "weighting": "frame_share",
    },
    {
        "grain": "full_session",
        "sex": "M",
        "metric": "delta_frac_near",
        "trial": "id_obj",
        "session_step": "BL->condition",
        "weighting": "frame_share",
    },
    {
        "grain": "full_session",
        "sex": "F",
        "metric": "delta_frac_near",
        "trial": "no_obj",
        "session_step": "BL->REC11hr",
        "weighting": "frame_share",
    },
)

COMPANION_B_SESSION = "NOR_REC3hr"
COMPANION_B_TRIAL = "no_obj"
COMPANION_B_METRIC = "shannon_bits"  # column `p` in shannon_level_kruskal


def _match(df: pd.DataFrame, key: dict[str, str]) -> pd.DataFrame:
    sub = df.copy()
    for col, val in key.items():
        sub = sub[sub[col].astype(str) == val]
    return sub


def run(out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sess = pd.read_csv(SESSION_LONG)
    a_rows: list[pd.DataFrame] = []
    for key in COMPANION_A_KEYS:
        hit = _match(sess, key)
        if len(hit) != 1:
            raise ValueError(f"Companion-A key not unique: {key} -> {len(hit)} rows")
        a_rows.append(hit)
    family_a = pd.concat(a_rows, ignore_index=True)
    family_a["family"] = "Composition-Companion-A"
    family_a = apply_bh(family_a)
    family_a.to_csv(out_dir / "composition_companion_a_tests.csv", index=False)

    sh = pd.read_csv(SHANNON_LEVEL)
    sub_b = sh[
        (sh["session"].astype(str) == COMPANION_B_SESSION)
        & (sh["trial"].astype(str) == COMPANION_B_TRIAL)
    ].copy()
    if sub_b.empty:
        raise ValueError("Companion-B: no Shannon level rows")
    sub_b["metric"] = COMPANION_B_METRIC
    sub_b["family"] = "Composition-Companion-B"
    sub_b = apply_bh(sub_b)
    sub_b.to_csv(out_dir / "composition_companion_b_tests.csv", index=False)

    n_a = int(family_a["hit_fdr05"].astype(bool).sum())
    n_b = int(sub_b["hit_fdr05"].astype(bool).sum())
    summary = {
        "Composition-Companion-A": {
            "family_size": len(COMPANION_A_KEYS),
            "n_hit_fdr05": n_a,
            "pass": bool(n_a == len(COMPANION_A_KEYS)),
        },
        "Composition-Companion-B": {
            "family_size": int(len(sub_b)),
            "n_hit_fdr05": n_b,
            "pass": bool(n_b > 0),
            "note": "consensus median-across-models Shannon level Kruskal",
        },
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main() -> int:
    run(DEFAULT_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
