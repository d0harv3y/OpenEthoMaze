"""Generate / stage vault-facing figures for verdict notes.

1. Honesty FDR panels from tests_long (null families).
2. Copy selected existing campaign figures into vault attachments/.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(r"D:/sack/datas/impress/moseq_251017/_nor_object_mi")
CROSSCORR = Path(r"D:/sack/crosscorr")
ATTACH = Path(r"C:/Users/admin/code/OpenEthoMaze/docs/vaults/openethomaze/attachments")
FIG_DIR = ROOT / "vault_verdict_figures"

# (attachment_stem, tests_csv, title, label_cols)
HONESTY_PANELS: list[tuple[str, Path, str, list[str]]] = [
    (
        "fig_v_visit_grammar_null",
        ROOT / "simpler_first_bout_grammar" / "bout_grammar_tests_long.csv",
        "BoutGrammar-A — visit grammar (0 FDR)",
        ["sex", "session", "metric"],
    ),
    (
        "fig_v_side_geometry_null",
        ROOT / "simpler_first_side_mass" / "side_mass_tests_long.csv",
        "SideMass-A — nvl-side geometry (0 FDR)",
        ["sex", "session", "metric"],
    ),
    (
        "fig_v_occupancy_delta_null",
        ROOT / "simpler_first_occupancy_session_delta" / "occupancy_session_delta_tests_long.csv",
        "OccSessDelta-A — BL→TX occupancy Δ (0 FDR)",
        ["sex", "metric"],
    ),
    (
        "fig_v_transstruct_null",
        ROOT / "simpler_first_transition_structure" / "transition_structure_tests_long.csv",
        "TransStruct-A — bout transition @ nvl_obj (0 FDR)",
        ["sex", "metric"],
    ),
    (
        "fig_v_transstruct_expanded_null",
        ROOT
        / "simpler_first_transition_structure_expanded"
        / "transition_structure_expanded_tests_long.csv",
        "TransStruct-B — joint expanded grains (0 FDR)",
        ["sex", "session", "trial", "metric"],
    ),
    (
        "fig_v_transstruct_full_grid_null",
        ROOT
        / "simpler_first_transition_structure_full_grid"
        / "transition_structure_full_grid_tests_long.csv",
        "TransStruct-C — joint full level grid (0 FDR)",
        ["sex", "session", "trial", "metric"],
    ),
    (
        "fig_v_transstruct_pergrain_null",
        ROOT
        / "simpler_first_sequence_per_grain_bh"
        / "transstruct_full_grid_per_grain_tests_long.csv",
        "TransStruct-PerGrain — m=4 per grain (0 FDR)",
        ["sex", "session", "trial", "metric"],
    ),
    (
        "fig_v_ngramseq_null",
        ROOT / "simpler_first_ngram_seq" / "ngram_seq_tests_long.csv",
        "NGramSeq-A — pair MI / bigram @ nvl_obj (0 FDR)",
        ["sex", "metric"],
    ),
    (
        "fig_v_ngramseq_expanded_null",
        ROOT / "simpler_first_ngram_seq_expanded" / "ngram_seq_expanded_tests_long.csv",
        "NGramSeq-B — joint expanded grains (0 FDR)",
        ["sex", "session", "trial", "metric"],
    ),
    (
        "fig_v_ngramseq_full_grid_null",
        ROOT / "simpler_first_ngram_seq_full_grid" / "ngram_seq_full_grid_tests_long.csv",
        "NGramSeq-C — joint full level grid (0 FDR)",
        ["sex", "session", "trial", "metric"],
    ),
    (
        "fig_v_ngramseq_pergrain_null",
        ROOT
        / "simpler_first_sequence_per_grain_bh"
        / "ngramseq_full_grid_per_grain_tests_long.csv",
        "NGramSeq-PerGrain — m=4 per grain (0 FDR)",
        ["sex", "session", "trial", "metric"],
    ),
    (
        "fig_v_residual_litmus_null",
        ROOT / "simpler_first_residual_litmus" / "residual_litmus_tests_long.csv",
        "Residual-A — Layer A residuals (0 FDR)",
        ["sex", "metric"],
    ),
    (
        "fig_v_composition_companion_a",
        ROOT
        / "simpler_first_composition_companion_audit"
        / "composition_companion_a_tests.csv",
        "Composition-Companion-A (session-step)",
        ["sex", "metric"],
    ),
    (
        "fig_v_composition_companion_b",
        ROOT
        / "simpler_first_composition_companion_audit"
        / "composition_companion_b_tests.csv",
        "Composition-Companion-B (Shannon REC3 no_obj)",
        ["sex"],
    ),
]

# Existing campaign figures → vault attachment name
COPIES: list[tuple[Path, str]] = [
    (
        ROOT
        / "simpler_first_condition_on_paired_delta"
        / "figures"
        / "fig_q5_engagement_delta_nor_tx_m.svg",
        "fig_q5_engagement_delta_nor_tx_m.svg",
    ),
    (
        ROOT
        / "simpler_first_condition_on_paired_delta"
        / "figures"
        / "fig_q5_engagement_delta_nor_tx_f.svg",
        "fig_q5_engagement_delta_nor_tx_f.svg",
    ),
    (
        ROOT
        / "simpler_first_object_prox_0p10"
        / "figures"
        / "fig_object_prox_consensus_kruskal.svg",
        "fig_v_recognition_lattice_dr_kruskal.svg",
    ),
    (
        ROOT
        / "simpler_first_object_prox_0p10"
        / "figures"
        / "fig_object_prox_occupancy_kruskal.svg",
        "fig_v_candidate_lattice_occupancy.svg",
    ),
    (
        ROOT
        / "simpler_first_object_prox_0p10"
        / "figures"
        / "fig_object_prox_consensus_wilcoxon.svg",
        "fig_v_assay_dr_vs0.svg",
    ),
    (
        ROOT
        / "simpler_first_condition_on_paired_delta"
        / "figures"
        / "fig_condition_consensus_animal_condition.svg",
        "fig_v_recognition_lattice_condition_consensus.svg",
    ),
    (
        CROSSCORR
        / "out_spearman_physio_x_bh"
        / "heatmaps"
        / "overview_NOR_TX-L.png",
        "fig_v_dr_physio_null_nor_tx_L.png",
    ),
    (
        CROSSCORR
        / "out_spearman_engagement_delta_physio"
        / "heatmaps"
        / "overview_engagement_delta_physL.png",
        "fig_v_engagement_physio_null_L.png",
    ),
]


def _cell_label(row: pd.Series, cols: list[str]) -> str:
    parts = []
    for c in cols:
        if c in row.index and pd.notna(row[c]):
            parts.append(str(row[c]))
    return " · ".join(parts)


def honesty_panel(df: pd.DataFrame, title: str, label_cols: list[str], out_svg: Path) -> None:
    need = {"p", "q_bh"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"{out_svg.name}: missing {missing}")
    d = df.copy()
    d["p"] = pd.to_numeric(d["p"], errors="coerce")
    d["q_bh"] = pd.to_numeric(d["q_bh"], errors="coerce")
    d = d.dropna(subset=["p", "q_bh"]).sort_values("p").reset_index(drop=True)
    if "hit_fdr05" not in d.columns:
        d["hit_fdr05"] = d["q_bh"] < 0.05
    else:
        d["hit_fdr05"] = d["hit_fdr05"].astype(bool)
    if "hit_p05" not in d.columns:
        d["hit_p05"] = d["p"] < 0.05
    else:
        d["hit_p05"] = d["hit_p05"].astype(bool)

    y = -np.log10(np.clip(d["p"].to_numpy(dtype=float), 1e-300, None))
    labels = [_cell_label(r, label_cols) for _, r in d.iterrows()]
    colors = []
    for _, r in d.iterrows():
        if bool(r["hit_fdr05"]):
            colors.append("#b22222")  # FDR hit
        elif bool(r["hit_p05"]):
            colors.append("#d4a017")  # uncorrected only
        else:
            colors.append("#6b7280")

    n = len(d)
    h = max(3.2, 0.28 * n + 1.8)
    fig, ax = plt.subplots(figsize=(9.5, h), layout="constrained")
    ypos = np.arange(n)
    ax.barh(ypos, y, color=colors, edgecolor="none", height=0.7)
    ax.axvline(-np.log10(0.05), color="#444", ls="--", lw=1, label="p = 0.05")
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel(r"−log₁₀(p)  (uncorrected)")
    ax.set_title(title, fontsize=11)
    # annotate q on the right of bars that are p05 or near
    for i, r in d.iterrows():
        if bool(r["hit_p05"]) or float(r["q_bh"]) < 0.25:
            ax.text(
                float(y[i]) + 0.03,
                i,
                f"q={float(r['q_bh']):.3f}",
                va="center",
                fontsize=6,
                color="#333",
            )
    n_fdr = int(d["hit_fdr05"].sum())
    n_p = int(d["hit_p05"].sum())
    ax.text(
        0.99,
        0.01,
        f"FDR hits {n_fdr}/{n} · uncorrected p<0.05: {n_p}/{n}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#333",
    )
    ax.legend(loc="lower right", fontsize=7, frameon=False)
    fig.savefig(out_svg, format="svg")
    plt.close(fig)


def main() -> None:
    ATTACH.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    for stem, csv_path, title, cols in HONESTY_PANELS:
        if not csv_path.is_file():
            print("SKIP missing", csv_path)
            continue
        df = pd.read_csv(csv_path)
        # companion audit may use different metric col names — keep flexible labels
        use_cols = [c for c in cols if c in df.columns]
        if not use_cols:
            use_cols = [c for c in ("sex", "metric", "grain") if c in df.columns]
        out = FIG_DIR / f"{stem}.svg"
        honesty_panel(df, title, use_cols, out)
        shutil.copy2(out, ATTACH / f"{stem}.svg")
        print("wrote", stem)

    for src, dest_name in COPIES:
        if not src.is_file():
            print("SKIP copy", src)
            continue
        shutil.copy2(src, ATTACH / dest_name)
        print("copied", dest_name)

    print("attachments:", ATTACH)


if __name__ == "__main__":
    main()
