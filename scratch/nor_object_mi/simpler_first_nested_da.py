"""Compose second-order paired DA Δp_k from existing 1st-order packs.

(b) session_on_trial: from ``simpler_first_da/da_syllable_deltas_per_animal.csv``
(c) trial_on_session: from ``simpler_first_phase_paired/phase_paired_da_deltas_per_animal.csv``

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/simpler_first_nested_da.py
  uv run python scratch/nor_object_mi/fig_cluster_tx_kruskal_nested.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.nested_da_delta import (  # noqa: E402
    compose_nested_deltas,
    load_condition_step_first_order,
    load_session_step_first_order,
    paired_n_by_outer_step,
)

DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_PP = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_phase_paired"
)


def _info_md(*, generated: str) -> str:
    return f"""# Nested paired Δp_k (2nd order) — data dictionary

Compose two within-animal pairings on syllable share Δp_k.

|                 |                                                                              |
| --------------- | ---------------------------------------------------------------------------- |
| Generated       | {generated}                                                                   |
| These files     | `sack/datas/impress/moseq_251017/_nor_object_mi/simpler_first_nested_da/` |
| How regenerated | `OpenEthoMaze/scratch/nor_object_mi/simpler_first_nested_da.py`             |

**Abbreviations:** DA = differential abundance; NOR = novel object recognition;
tx = treatment (`noSD`/`GHSD`/`RBSD`); BH = Benjamini–Hochberg; Kruskal = Kruskal–Wallis;
kpMS = keypoint-MoSeq.

## Estimands

| Axis | Stage A (1st) | Stage A (2nd) | Question (plain) |
| ---- | ------------- | ------------- | ---------------- |
| **b** `session_on_trial` | condition-step Δ at each phase | phase-step on that Δ | Does **presence/novelty/span reallocation** change across protocol? |
| **c** `trial_on_session` | phase-step Δ at each condition | condition-step on that Δ | Does **BL→TX (etc.) shift** differ across arena layouts? |

```
Δ²p_k = δ_k(right outer) − δ_k(left outer)
δ_k = first-order paired Δp_k from the sibling pack
```

## b and c are one lattice (transpose)

For **one atomic condition step × one atomic phase step**, (b) and (c) yield the **same** Δ²p_k per animal and the **same** paired n (four-endpoint intersection). Nesting order **commutes** — the 2×2 algebra is one interaction contrast; heatmaps differ only in **which axis is faceted vs columned**. Do **not** report (b) and (c) as independent findings; pick one layout for the claim.

Vocab: `Documents/work/vocab/CONTEXT.md` (nested pairing on two axes), `FORMULAS.md` (second-order paired change), `STATS.md` / `INTERPRET.md` (two pairing axes).

Stage B (cluster-13 model overview): Kruskal Δ²p ~ tx within sex — **not** Wilcoxon vs 0.

## Inputs

| File | Role |
| ---- | ---- |
| `../simpler_first_da/da_syllable_deltas_per_animal.csv` | 1st-order condition-step |
| `../simpler_first_phase_paired/phase_paired_da_deltas_per_animal.csv` | 1st-order phase-step |

## Outputs

| File | Content |
| ---- | ------- |
| `nested_b_da_deltas_per_animal.csv` | (b) animal × syllable × model |
| `nested_c_da_deltas_per_animal.csv` | (c) animal × syllable × model |
| `nested_b_paired_n.json` | paired n by phase step |
| `nested_c_paired_n.json` | paired n by condition step |

Figures: `fig_cluster_tx_kruskal_nested.py` → `figures/fig_nested_*_cluster13_model_tx_kruskal_overview.*`
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--pp-dir", type=Path, default=DEFAULT_PP)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    art_root = args.da_dir.parent
    out = args.out_dir or (art_root / "simpler_first_nested_da")
    out.mkdir(parents=True, exist_ok=True)

    print("load 1st-order condition-step deltas ...", flush=True)
    d_cond = load_condition_step_first_order(args.da_dir)
    print("compose (b) session_on_trial ...", flush=True)
    nested_b = compose_nested_deltas(d_cond, axis="session_on_trial")
    nested_b.to_csv(out / "nested_b_da_deltas_per_animal.csv", index=False)

    print("load 1st-order phase-step deltas ...", flush=True)
    d_phase = load_session_step_first_order(args.pp_dir)
    print("compose (c) trial_on_session ...", flush=True)
    nested_c = compose_nested_deltas(d_phase, axis="trial_on_session")
    nested_c.to_csv(out / "nested_c_da_deltas_per_animal.csv", index=False)

    n_b = paired_n_by_outer_step(nested_b, axis="session_on_trial")
    n_c = paired_n_by_outer_step(nested_c, axis="trial_on_session")
    (out / "nested_b_paired_n.json").write_text(json.dumps(n_b, indent=2), encoding="utf-8")
    (out / "nested_c_paired_n.json").write_text(json.dumps(n_c, indent=2), encoding="utf-8")
    (out / "INFO_nested_da.md").write_text(_info_md(generated=date.today().isoformat()), encoding="utf-8")

    summary = {
        "n_nested_b_rows": int(len(nested_b)),
        "n_nested_c_rows": int(len(nested_c)),
        "n_models_b": int(nested_b["model"].nunique()) if not nested_b.empty else 0,
        "paired_n_b": n_b,
        "paired_n_c": n_c,
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
