#!/usr/bin/env python3
"""PROTOTYPE — render bout HMM results to PNG + text (one-shot)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

_SCRATCH = Path(__file__).resolve().parent
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from bout_hmm_logic import (
    build_trial_sequence,
    fit_sticky_hmm,
    load_cluster_lookup,
    load_trial_bouts,
    summarize_decode,
)

MANIFEST = Path(
    r"C:\Users\admin\Documents\work\sack\test2\behavior_ethogram\phase_i\calibration\bout_manifest_long.csv"
)
PROTOTYPE = Path(
    r"C:\Users\admin\Documents\work\sack\test2\behavior_ethogram\phase_i\calibration\prototype_hdbscan_features.csv"
)
OUT_DIR = _SCRATCH / "output" / "prototype_bout_hmm"
TRIAL = "3394/S02/T07"
STREAM = "anatomical"
SEED = "042"
N_STATES = 5
KAPPA = 8.0


def _color_strip(labels: np.ndarray, cmap_name: str = "tab20") -> np.ndarray:
    uniq = sorted(set(int(x) for x in labels))
    cmap = plt.get_cmap(cmap_name, max(len(uniq), 1))
    lut = {u: cmap(i) for i, u in enumerate(uniq)}
    return np.array([lut[int(v)] for v in labels])


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bouts = load_trial_bouts(MANIFEST, stream=STREAM, seed=SEED, trial_key=TRIAL)
    lookup = load_cluster_lookup(PROTOTYPE, stream=STREAM, seed=SEED)

    configs = [
        ("kin_only", False),
        ("kin_plus_syllable", True),
    ]
    results: dict[str, object] = {"trial_key": TRIAL, "stream": STREAM, "seed": SEED, "runs": {}}

    fig, axes = plt.subplots(len(configs), 1, figsize=(14, 2.2 * len(configs)), sharex=True)
    if len(configs) == 1:
        axes = [axes]

    for ax, (name, inc_syl) in zip(axes, configs, strict=True):
        seq = build_trial_sequence(bouts, cluster_lookup=lookup, include_syllable=inc_syl)
        model, states, loglik = fit_sticky_hmm(
            seq.features, n_states=N_STATES, kappa=KAPPA, seed=42
        )
        summary = summarize_decode(seq, states)
        t = np.arange(len(seq.bouts))

        ax.imshow(
            _color_strip(seq.syllable_ids)[None, :, :],
            aspect="auto",
            extent=[0, len(t), 3, 4],
            interpolation="nearest",
        )
        ax.imshow(
            _color_strip(seq.cluster_ids, "Set2")[None, :, :],
            aspect="auto",
            extent=[0, len(t), 2, 3],
            interpolation="nearest",
        )
        ax.imshow(
            _color_strip(states, "viridis")[None, :, :],
            aspect="auto",
            extent=[0, len(t), 1, 2],
            interpolation="nearest",
        )
        ax.set_yticks([1.5, 2.5, 3.5])
        ax.set_yticklabels(["HMM state", "cluster", "syllable"])
        ax.set_ylabel(name.replace("_", " "))
        ax.set_title(
            f"K={N_STATES} κ={KAPPA}  boundaries: syll={summary['boundaries_syllable']} "
            f"cluster={summary['boundaries_cluster']} hmm={summary['boundaries_hmm']}"
        )

        # speed trace colored by HMM state
        speeds = np.array([b.bout_mean_speed_mps for b in seq.bouts])
        ax2 = ax.twinx()
        ax2.plot(t, speeds, color="0.4", lw=0.8, alpha=0.7)
        ax2.set_ylabel("m/s", fontsize=8)
        ax2.tick_params(labelsize=7)

        state_stats = []
        for sid in sorted(summary["hmm_state_mean_speed_mps"]):
            mask = states == sid
            state_stats.append(
                {
                    "state": int(sid),
                    "n_bouts": int(mask.sum()),
                    "mean_speed_mps": round(summary["hmm_state_mean_speed_mps"][sid], 4),
                    "mean_dheading": round(float(np.mean([seq.bouts[i].bout_mean_abs_dheading for i in np.flatnonzero(mask)])), 4) if mask.any() else 0.0,
                    "mean_frames": round(float(np.mean([seq.bouts[i].bout_frames for i in np.flatnonzero(mask)])), 1) if mask.any() else 0.0,
                }
            )

        results["runs"][name] = {
            "include_syllable": inc_syl,
            "loglik": round(loglik, 2),
            "summary": {k: (v if not isinstance(v, dict) else {str(a): b for a, b in v.items()}) for k, v in summary.items()},
            "state_stats": state_stats,
            "decoded_states": states.tolist(),
            "syllable_ids": seq.syllable_ids.tolist(),
            "cluster_ids": seq.cluster_ids.tolist(),
        }

    axes[-1].set_xlabel("bout index (time →)")
    fig.suptitle(f"PROTOTYPE bout HMM — {TRIAL} ({STREAM} seed {SEED})", fontsize=12, y=1.02)
    fig.tight_layout()
    png_path = OUT_DIR / f"{TRIAL.replace('/', '_')}_bout_hmm.png"
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    json_path = OUT_DIR / f"{TRIAL.replace('/', '_')}_bout_hmm.json"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # compact text report
    lines = [
        f"# Bout HMM prototype results — {TRIAL}",
        f"stream={STREAM} seed={SEED} K={N_STATES} kappa={KAPPA}",
        "",
    ]
    for name, run in results["runs"].items():
        lines.append(f"## {name}")
        s = run["summary"]
        lines.append(f"- loglik: {run['loglik']}")
        lines.append(f"- boundaries: syllable={s['boundaries_syllable']} cluster={s['boundaries_cluster']} hmm={s['boundaries_hmm']} coincide={s['boundary_coincide_hmm_cluster']}")
        lines.append("- state stats:")
        for st in run["state_stats"]:
            lines.append(
                f"  - state {st['state']}: n={st['n_bouts']} speed={st['mean_speed_mps']} m/s "
                f"dheading={st['mean_dheading']} frames={st['mean_frames']}"
            )
        lines.append("")
    md_path = OUT_DIR / f"{TRIAL.replace('/', '_')}_bout_hmm.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(md_path.read_text(encoding="utf-8"))
    print(f"PNG: {png_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
