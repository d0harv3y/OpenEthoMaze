"""Sex-stratified tx tests on presence Δ, per phase and pooled across BL+TX."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

Metric = "delta_excess_present_minus_absent"


def _load(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {str(r["animal_id"]): r for r in csv.DictReader(f)}


def _tx_tests(
    rows: list[dict[str, object]],
    *,
    sex_stratum: str,
) -> list[dict[str, object]]:
    by_tx: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        tx = str(r.get("tx", "") or "")
        if not tx:
            continue
        val = float(r[Metric])
        if np.isfinite(val):
            by_tx[tx].append(val)
    levels = sorted(by_tx)
    out: list[dict[str, object]] = []
    if len(levels) < 2:
        return out
    samples = [by_tx[t] for t in levels]
    if len(levels) == 2:
        a, b = levels
        stat, p = stats.mannwhitneyu(by_tx[a], by_tx[b], alternative="two-sided")
        out.append(
            {
                "sex_stratum": sex_stratum,
                "factor": "tx",
                "level_a": a,
                "level_b": b,
                "n_a": len(by_tx[a]),
                "n_b": len(by_tx[b]),
                "median_a": float(np.median(by_tx[a])),
                "median_b": float(np.median(by_tx[b])),
                "stat": float(stat),
                "p": float(p),
                "test": "mannwhitneyu",
            }
        )
        return out
    stat, p = stats.kruskal(*samples)
    all_vals = [v for s in samples for v in s]
    out.append(
        {
            "sex_stratum": sex_stratum,
            "factor": "tx",
            "level_a": "|".join(levels),
            "level_b": "",
            "n_a": len(all_vals),
            "n_b": 0,
            "median_a": float(np.median(all_vals)),
            "median_b": float("nan"),
            "stat": float(stat),
            "p": float(p),
            "test": "kruskal",
        }
    )
    for i, a in enumerate(levels):
        for b in levels[i + 1 :]:
            stat_pw, p_pw = stats.mannwhitneyu(by_tx[a], by_tx[b], alternative="two-sided")
            out.append(
                {
                    "sex_stratum": sex_stratum,
                    "factor": "tx",
                    "level_a": a,
                    "level_b": b,
                    "n_a": len(by_tx[a]),
                    "n_b": len(by_tx[b]),
                    "median_a": float(np.median(by_tx[a])),
                    "median_b": float(np.median(by_tx[b])),
                    "stat": float(stat_pw),
                    "p": float(p_pw),
                    "test": "mannwhitneyu_pairwise",
                }
            )
    return out


def _run_by_sex(rows: list[dict[str, object]], *, phase_label: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for sex in ("F", "M"):
        subset = [r for r in rows if str(r.get("sex", "")) == sex]
        for row in _tx_tests(subset, sex_stratum=sex):
            row = dict(row)
            row["phase"] = phase_label
            row["metric"] = Metric
            out.append(row)
    # also pooled sexes for reference
    for row in _tx_tests(rows, sex_stratum="all"):
        row = dict(row)
        row["phase"] = phase_label
        row["metric"] = Metric
        out.append(row)
    return out


def _cell_table(rows: list[dict[str, object]], *, phase_label: str) -> list[dict[str, object]]:
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        cells[(str(r["sex"]), str(r["tx"]))].append(float(r[Metric]))
    out = []
    for (sex, tx), vals in sorted(cells.items()):
        arr = np.asarray(vals, dtype=np.float64)
        out.append(
            {
                "phase": phase_label,
                "sex": sex,
                "tx": tx,
                "n": len(arr),
                "median_delta": float(np.median(arr)),
                "mean_delta": float(np.mean(arr)),
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(
        r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
        r"\_nor_object_mi\paramscan_s1-1e8_s2-1e5_ss-50"
    )
    ap.add_argument("--tx-csv", type=Path, default=root / "presence" / "mi_delta_presence_per_animal.csv")
    ap.add_argument(
        "--bl-csv", type=Path, default=root / "presence_NOR_BL" / "mi_delta_presence_per_animal.csv"
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=root / "presence_phase_pooled",
    )
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    tx_map = _load(args.tx_csv)
    bl_map = _load(args.bl_csv)
    shared = sorted(set(tx_map) & set(bl_map))

    rows_tx = [
        {
            "animal_id": aid,
            "sex": tx_map[aid]["sex"],
            "tx": tx_map[aid]["tx"],
            Metric: float(tx_map[aid][Metric]),
        }
        for aid in shared
    ]
    rows_bl = [
        {
            "animal_id": aid,
            "sex": bl_map[aid]["sex"],
            "tx": bl_map[aid]["tx"],
            Metric: float(bl_map[aid][Metric]),
        }
        for aid in shared
    ]
    rows_pool = []
    for aid in shared:
        d_tx = float(tx_map[aid][Metric])
        d_bl = float(bl_map[aid][Metric])
        rows_pool.append(
            {
                "animal_id": aid,
                "sex": tx_map[aid]["sex"],
                "tx": tx_map[aid]["tx"],
                "delta_tx": d_tx,
                "delta_bl": d_bl,
                Metric: 0.5 * (d_tx + d_bl),
            }
        )

    tests = []
    tests.extend(_run_by_sex(rows_tx, phase_label="NOR_TX"))
    tests.extend(_run_by_sex(rows_bl, phase_label="NOR_BL"))
    tests.extend(_run_by_sex(rows_pool, phase_label="BL_TX_mean"))

    cells = []
    cells.extend(_cell_table(rows_tx, phase_label="NOR_TX"))
    cells.extend(_cell_table(rows_bl, phase_label="NOR_BL"))
    cells.extend(_cell_table(rows_pool, phase_label="BL_TX_mean"))

    test_fields = [
        "phase",
        "sex_stratum",
        "factor",
        "level_a",
        "level_b",
        "n_a",
        "n_b",
        "median_a",
        "median_b",
        "stat",
        "p",
        "test",
        "metric",
    ]
    with (args.out_dir / "tx_tests_by_sex.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=test_fields, extrasaction="ignore")
        w.writeheader()
        for row in tests:
            w.writerow(row)

    cell_fields = ["phase", "sex", "tx", "n", "median_delta", "mean_delta"]
    with (args.out_dir / "delta_cells_by_sex_tx.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cell_fields)
        w.writeheader()
        for row in cells:
            w.writerow(row)

    pool_fields = ["animal_id", "sex", "tx", "delta_bl", "delta_tx", Metric]
    with (args.out_dir / "delta_bl_tx_mean_per_animal.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=pool_fields)
        w.writeheader()
        for row in rows_pool:
            w.writerow(row)

    # stdout summary: sex-stratified only
    print(f"n_shared_animals={len(shared)}")
    print("sex-stratified tx tests (Kruskal + pairwise):")
    for row in tests:
        if row["sex_stratum"] == "all":
            continue
        if row["test"] == "kruskal" or row["level_b"]:
            lb = row["level_b"] or ""
            print(
                f"  {row['phase']:11} sex={row['sex_stratum']}  "
                f"{row['level_a']:16} {lb:6}  "
                f"n={row['n_a']}/{row['n_b']}  "
                f"med={float(row['median_a']):+.4f}"
                + (f"/{float(row['median_b']):+.4f}" if lb else "")
                + f"  p={float(row['p']):.4g}  [{row['test']}]"
            )
    print("cell medians (BL_TX_mean):")
    for row in cells:
        if row["phase"] != "BL_TX_mean":
            continue
        print(
            f"  {row['sex']}|{row['tx']}: n={row['n']} median={float(row['median_delta']):+.4f}"
        )
    print(f"wrote {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
