"""Insert ## Figure sections into vault verdict notes."""

from __future__ import annotations

from pathlib import Path

Q = Path(r"C:/Users/admin/code/OpenEthoMaze/docs/vaults/openethomaze/questions")

FIGS: dict[str, list[tuple[str, str]]] = {
    "V Visit Grammar Null.md": [
        (
            "Honesty panel — BoutGrammar-A cells (−log₁₀ p; gold = uncorrected-only, red = FDR). Source: [[Run Bout Grammar]].",
            "fig_v_visit_grammar_null",
        ),
    ],
    "V Side Geometry Null.md": [
        (
            "Honesty panel — SideMass-A. Source: [[Run Side Mass]].",
            "fig_v_side_geometry_null",
        ),
    ],
    "V Occupancy Delta Null.md": [
        (
            "Honesty panel — OccSessDelta-A. Source: [[Run Occupancy Session Delta]].",
            "fig_v_occupancy_delta_null",
        ),
    ],
    "V TransStruct Null.md": [
        (
            "Honesty panel — TransStruct-A (m=4). Source: [[Run Transition Structure]].",
            "fig_v_transstruct_null",
        ),
    ],
    "V TransStruct Expanded Null.md": [
        (
            "Honesty panel — TransStruct-B joint (m=24). Source: [[Run Transition Structure Expanded]].",
            "fig_v_transstruct_expanded_null",
        ),
    ],
    "V TransStruct Full Grid Null.md": [
        (
            "Honesty panel — TransStruct-C joint (m=48). Source: [[Run Transition Structure Full Grid]].",
            "fig_v_transstruct_full_grid_null",
        ),
    ],
    "V TransStruct PerGrain Null.md": [
        (
            "Honesty panel — TransStruct-PerGrain (m=4 within each grain). Source: [[Run Sequence PerGrain BH]].",
            "fig_v_transstruct_pergrain_null",
        ),
    ],
    "V NGramSeq Null.md": [
        (
            "Honesty panel — NGramSeq-A. Source: [[Run NGramSeq]].",
            "fig_v_ngramseq_null",
        ),
    ],
    "V NGramSeq Expanded Null.md": [
        (
            "Honesty panel — NGramSeq-B joint. Source: [[Run NGramSeq Expanded]].",
            "fig_v_ngramseq_expanded_null",
        ),
    ],
    "V NGramSeq Full Grid Null.md": [
        (
            "Honesty panel — NGramSeq-C joint. Source: [[Run NGramSeq Full Grid]].",
            "fig_v_ngramseq_full_grid_null",
        ),
    ],
    "V NGramSeq PerGrain Null.md": [
        (
            "Honesty panel — NGramSeq-PerGrain. Source: [[Run Sequence PerGrain BH]].",
            "fig_v_ngramseq_pergrain_null",
        ),
    ],
    "V Residual Litmus Null.md": [
        (
            "Honesty panel — Residual-A. Source: [[Run Residual Litmus]].",
            "fig_v_residual_litmus_null",
        ),
    ],
    "V Composition Companion Partial.md": [
        (
            "Companion-A session-step cells (FDR hits in red). Source: [[Run Composition Companion Audit]].",
            "fig_v_composition_companion_a",
        ),
        (
            "Companion-B Shannon at NOR_REC3hr × no_obj (M hit / F miss).",
            "fig_v_composition_companion_b",
        ),
    ],
    "V Recognition Lattice Null.md": [
        (
            "Object-prox DR × condition Kruskal (consensus) — DR miss. Source: [[Run Object Prox DR]].",
            "fig_v_recognition_lattice_dr_kruskal",
        ),
        (
            "Condition consensus animal lattice — novelty-step empty among FDR hits. Source: [[Run Condition on Paired Delta]].",
            "fig_v_recognition_lattice_condition_consensus",
        ),
    ],
    "V Candidate Lattice Null.md": [
        (
            "Object-prox occupancy Kruskal (consensus) — Family A near-miss zone, 0 FDR. Source: [[Run Object Prox DR]].",
            "fig_v_candidate_lattice_occupancy",
        ),
    ],
    "V DR Physio Null.md": [
        (
            "Physio × NOR overview heatmap at NOR_TX / light — sparse locomotorish hits, not DR. Source: [[Run Crosscorr Spearman]].",
            "fig_v_dr_physio_null_nor_tx_L",
        ),
    ],
    "V Engagement Physio Null.md": [
        (
            "Engagement Δ × physio overview (light phase) — M×locked null. Source: [[Run Crosscorr Spearman]].",
            "fig_v_engagement_physio_null_L",
        ),
    ],
    "V Near Misses Watchlist.md": [
        (
            "Visit-grammar honesty panel (includes F REC11 visit-duration near miss).",
            "fig_v_visit_grammar_null",
        ),
        (
            "Side-mass honesty panel (includes F TX near misses).",
            "fig_v_side_geometry_null",
        ),
        (
            "Occupancy-Δ honesty panel (includes M novel-Δ near miss).",
            "fig_v_occupancy_delta_null",
        ),
    ],
    "V TransStruct Cross-Campaign.md": [
        (
            "Locked ladder TransStruct-A honesty panel (cross-campaign does not overturn this). Source: [[Run Transition Structure]].",
            "fig_v_transstruct_null",
        ),
    ],
    "V TransStruct Raw Exploratory.md": [
        (
            "Locked portable-cluster TransStruct-A null (raw grid is exploratory cousin). Source: [[Run Transition Structure]].",
            "fig_v_transstruct_null",
        ),
    ],
}


def figure_block(items: list[tuple[str, str]]) -> str:
    lines = ["## Figure", ""]
    for cap, stem in items:
        lines.append(cap)
        lines.append("")
        lines.append(f"![[{stem}]]")
        lines.append("")
    lines.append(
        "Regen / campaign copies: `sack/.../vault_verdict_figures/` · "
        "`scratch/nor_object_mi/fig_vault_verdict_panels.py` · vault `attachments/`."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    for name, items in FIGS.items():
        path = Q / name
        text = path.read_text(encoding="utf-8")
        if name == "V Engagement Delta Treasure.md":
            print("skip", name)
            continue
        if "\n## Figure\n" in text:
            # strip prior Figure section
            start = text.index("\n## Figure\n")
            rest = text[start + 1 :]
            end_rel = None
            for marker in ("\n## Related", "\n## Keep", "\n#lava"):
                if marker in rest:
                    idx = rest.index(marker)
                    end_rel = start + 1 + idx if end_rel is None else min(end_rel, start + 1 + idx)
            if end_rel is None:
                text = text[:start] + "\n"
            else:
                text = text[:start] + "\n" + text[end_rel:]
        block = figure_block(items)
        if "\n## Related" in text:
            text = text.replace("\n## Related", "\n" + block + "\n## Related", 1)
        elif "\n## Keep" in text:
            text = text.replace("\n## Keep", "\n" + block + "\n## Keep", 1)
        else:
            text = text.rstrip() + "\n\n" + block
        path.write_text(text, encoding="utf-8", newline="\n")
        print("patched", name)


if __name__ == "__main__":
    main()
