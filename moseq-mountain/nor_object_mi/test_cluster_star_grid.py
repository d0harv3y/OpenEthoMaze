"""Litmus for multi-star cluster grid selection."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.cluster_star_grid import (  # noqa: E402
    clusters_with_min_stars,
    pick_jobs,
)


def test_clusters_with_min_stars_union(tmp_path: Path) -> None:
    da = pd.DataFrame(
        {
            "cluster_id": [30, 30, 13],
            "hit_fdr05": [True, True, True],
        }
    )
    pp = pd.DataFrame(
        {
            "cluster_id": [30, 47, 47],
            "hit_fdr05": [True, True, True],
        }
    )
    da_p = tmp_path / "da.csv"
    pp_p = tmp_path / "pp.csv"
    da.to_csv(da_p, index=False)
    pp.to_csv(pp_p, index=False)
    u = clusters_with_min_stars(da_p, pp_p, min_stars=2, source="union")
    assert set(u["cluster_id"].astype(int)) == {30, 47}
    row30 = u.loc[u["cluster_id"] == 30].iloc[0]
    assert int(row30["n_stars"]) == 3
    assert int(row30["n_da"]) == 2
    assert int(row30["n_pp"]) == 1


def test_pick_jobs_one_per_cluster() -> None:
    proto = pd.DataFrame(
        {
            "model": ["m1", "m1", "m2", "m2"],
            "cluster_id": [30, 30, 30, 47],
            "raw_syllable_id": [1, 2, 3, 4],
            "n_bouts": [10, 50, 40, 100],
        }
    )
    one = pick_jobs(proto, [30, 47], all_models=False)
    assert len(one) == 2
    r30 = one.loc[one["cluster_id"] == 30].iloc[0]
    assert int(r30["raw_syllable_id"]) == 2  # max n_bouts within m1×30, then max model
    # model m1 has syll2 with 50; m2 has syll3 with 40 → pick m1
    assert r30["model"] == "m1"
    allm = pick_jobs(proto, [30], all_models=True)
    assert len(allm) == 2
