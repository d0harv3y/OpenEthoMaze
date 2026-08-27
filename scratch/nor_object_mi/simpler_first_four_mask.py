"""Four-mask tx hunt (locked kpMS; all three conditions).

Masks are bout-level: locomotor majority × bout-mean dist < 0.10 m.
Primary: Welch ANOVA of (TX − BL) by tx on novel_obj. Gates: identical_obj,
no_obj, and BL level. Not frame-level investigation; not DA.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/simpler_first_four_mask.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.four_mask import (  # noqa: E402
    MASKS,
    gate_hits,
    hunt_tests,
    label_syllable_bouts,
    paired_tx_minus_bl,
    session_mask_table,
    session_rasters,
)
from nor_object_mi.simpler_first_presence import CONDS, NEAR_R_M  # noqa: E402
from nor_object_mi.simpler_first_q1 import LOCKED  # noqa: E402
from nor_object_mi.simpler_first_syll_ambulation_overlap import (  # noqa: E402
    AMB_COLS,
    DEFAULT_MOVE,
    DEFAULT_STILL,
    DEFAULT_SYLL,
    SYLL_COLS,
)

DEFAULT_OUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_four_mask"
)

SYLL_COLS_MASK = (*SYLL_COLS, "bout_mean_dist_any_m")


def load_locked_syllable_all_conds(path: Path, *, model: str) -> pd.DataFrame:
    chunks: list[pd.DataFrame] = []
    kept = 0
    for chunk in pd.read_csv(path, usecols=list(SYLL_COLS_MASK), chunksize=250_000):
        sub = chunk[chunk["model"] == model]
        if not sub.empty:
            chunks.append(sub)
            kept += len(sub)
        print(f"  syll chunk kept={kept:,}", flush=True)
    if not chunks:
        return pd.DataFrame(columns=list(SYLL_COLS_MASK))
    out = pd.concat(chunks, ignore_index=True)
    out["animal_id"] = out["animal_id"].astype(str)
    return out


def _info_md() -> str:
    return """# INFO — four-mask tx hunt

## What this is

Bout-level masks on the locked kpMS (keypoint-MoSeq) model:

1. `still_near` — majority still ∩ bout-mean spot→nearest-target < 0.10 m
2. `move_near`
3. `move_far`
4. `still_far`

Grain: animal × phase × condition. Scalars: `frac_mask` (mask frames / session
syllable frames) and Shannon bits of the frame-weighted composition inside the
mask.

**Tx hunt (inferential):** Welch ANOVA of (TX − BL) by tx on `novel_obj`,
within sex. BH (Benjamini–Hochberg) family = 4 masks × 2 metrics within sex.
Companion: one-sample t of Δ vs 0 (treatments pooled).

**Gates (veto, not in the BH family):** same ANOVA must miss on `identical_obj`
and `no_obj`; ANOVA of BL level by tx must miss on novel. `tx_specific` =
novel ANOVA FDR hit and gates miss.

## What this is not

Not investigation (near is bout-mean, not frame-level). Not DA. Ids are not
portable across models. Masking is a *where* cut, not a p-value factory.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--syllable-csv", type=Path, default=DEFAULT_SYLL)
    ap.add_argument("--movement-csv", type=Path, default=DEFAULT_MOVE)
    ap.add_argument("--immobile-csv", type=Path, default=DEFAULT_STILL)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--model", type=str, default=str(LOCKED["model"]))
    ap.add_argument("--near-m", type=float, default=NEAR_R_M)
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    model = str(args.model)
    print(f"Loading locked syllables model={model} (all conditions)", flush=True)
    syll = load_locked_syllable_all_conds(args.syllable_csv, model=model)
    print(f"syllable bouts={len(syll):,}", flush=True)
    print("Loading movement / immobile", flush=True)
    move = pd.read_csv(args.movement_csv, usecols=list(AMB_COLS))
    still = pd.read_csv(args.immobile_csv, usecols=list(AMB_COLS))
    print("Building locomotor rasters", flush=True)
    rasters = session_rasters(move, still)
    print(f"sessions with raster={len(rasters):,}", flush=True)
    print("Labeling syllable bouts", flush=True)
    labeled = label_syllable_bouts(syll, rasters, r_m=float(args.near_m))
    sessions = session_mask_table(labeled)
    sessions.to_csv(out / "session_mask_scalars.csv", index=False)
    paired = paired_tx_minus_bl(sessions)
    paired.to_csv(out / "paired_tx_minus_bl.csv", index=False)
    tests = hunt_tests(paired)
    tests.to_csv(out / "hunt_tests.csv", index=False)
    gates = gate_hits(tests)
    gates.to_csv(out / "gate_hits.csv", index=False)
    n_spec = int(gates["tx_specific"].sum()) if not gates.empty else 0
    blob = {
        "model": model,
        "near_m": float(args.near_m),
        "masks": list(MASKS),
        "conditions": list(CONDS),
        "n_syllable_bouts": int(len(labeled)),
        "n_session_mask_rows": int(len(sessions)),
        "n_paired": int(len(paired)),
        "n_tests": int(len(tests)),
        "n_tx_specific": n_spec,
        "not": ["investigation", "DA", "portable_ids"],
    }
    (out / "run_summary.json").write_text(json.dumps(blob, indent=2), encoding="utf-8")
    (out / "INFO_four_mask.md").write_text(_info_md(), encoding="utf-8")
    print(f"tx_specific={n_spec} -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
