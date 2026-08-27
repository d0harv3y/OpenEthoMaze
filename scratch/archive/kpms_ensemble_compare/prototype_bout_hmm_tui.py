#!/usr/bin/env python3
"""PROTOTYPE — interactive bout-level sticky HMM on one trial.

Run (PowerShell):
  uv run python scratch/kpms_ensemble_compare/prototype_bout_hmm_tui.py

Question: does bout-sequence HMM segmentation feel more behavior-coherent than
prototype HDBSCAN cluster labels on the same trial?

Keys: [n/p] bout  [+/-] states  [[/]] stickiness  [s] syllable feature  [r] refit  [q] quit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_SCRATCH = Path(__file__).resolve().parent
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from bout_hmm_logic import (  # noqa: E402
    build_trial_sequence,
    fit_sticky_hmm,
    load_cluster_lookup,
    load_trial_bouts,
    summarize_decode,
)

DEFAULT_MANIFEST = Path(
    r"C:\Users\admin\Documents\work\sack\test2\behavior_ethogram\phase_i\calibration\bout_manifest_long.csv"
)
DEFAULT_PROTOTYPE = Path(
    r"C:\Users\admin\Documents\work\sack\test2\behavior_ethogram\phase_i\calibration\prototype_hdbscan_features.csv"
)
DEFAULT_TRIAL = "3394/S02/T07"
DEFAULT_STREAM = "anatomical"
DEFAULT_SEED = "042"

BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"
CLEAR = "\033[2J\033[H"


def _read_key() -> str:
    try:
        import msvcrt

        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            msvcrt.getch()
            return ""
        return ch.decode("utf-8", errors="ignore").lower()
    except ImportError:
        return input("> ").strip().lower()[:1]


def _bar(labels: np.ndarray, width: int = 72) -> str:
    if labels.size == 0:
        return ""
    uniq = sorted(set(labels.tolist()))
    palette = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    cmap = {u: palette[i % len(palette)] for i, u in enumerate(uniq)}
    if labels.size <= width:
        chars = [cmap[int(v)] for v in labels]
    else:
        step = labels.size / width
        chars = [cmap[int(labels[int(i * step)])] for i in range(width)]
    return "".join(chars)


def _cedilla_row(seq, cursor: int, width: int = 72) -> str:
    n = len(seq.bouts)
    if n <= width:
        marks = ["^" if i == cursor else " " for i in range(n)]
    else:
        marks = [" "] * width
        pos = int(cursor / n * width)
        marks[min(pos, width - 1)] = "^"
    return "".join(marks)


def render(
    *,
    seq,
    hmm_states: np.ndarray,
    cursor: int,
    n_states: int,
    kappa: float,
    include_syllable: bool,
    loglik: float,
    summary: dict[str, object],
) -> None:
    bout = seq.bouts[cursor]
    print(CLEAR, end="")
    print(f"{BOLD}PROTOTYPE bout-level sticky HMM{RESET}  {DIM}(throwaway — delete when done){RESET}")
    print()
    print(f"{BOLD}trial{RESET}     {bout.trial_key}  stream={bout.stream} seed={bout.seed}")
    print(f"{BOLD}bout{RESET}      {cursor + 1}/{len(seq.bouts)}  frames={bout.bout_frames}  phase={bout.bout_primary_state}")
    print(f"{BOLD}kinematics{RESET} speed={bout.bout_mean_speed_mps:.4f} m/s  dheading={bout.bout_mean_abs_dheading:.3f}  still={bout.bout_frac_still:.2f}")
    print()
    print(f"{BOLD}model{RESET}     K={n_states}  kappa={kappa:.1f}  features={'kin+syllable' if include_syllable else 'kin only'}  loglik={loglik:.1f}")
    print(f"{BOLD}summary{RESET}   syll_bnd={summary['boundaries_syllable']}  cluster_bnd={summary['boundaries_cluster']}  hmm_bnd={summary['boundaries_hmm']}  coincide={summary['boundary_coincide_hmm_cluster']}")
    speeds = summary["hmm_state_mean_speed_mps"]
    speed_txt = "  ".join(f"s{k}={v:.3f}" for k, v in sorted(speeds.items()))
    print(f"{DIM}HMM state mean speeds (m/s): {speed_txt}{RESET}")
    print()
    syl = int(seq.syllable_ids[cursor])
    clu = int(seq.cluster_ids[cursor])
    hmm = int(hmm_states[cursor])
    print(f"{BOLD}@cursor{RESET}   syllable={syl}  cluster={clu}  hmm_state={hmm}")
    print()
    print(f"{BOLD}syllable{RESET}  {_bar(seq.syllable_ids)}")
    print(f"{BOLD}cluster{RESET}   {_bar(seq.cluster_ids)}")
    print(f"{BOLD}hmm{RESET}       {_bar(hmm_states)}")
    print(f"{DIM}cursor{RESET}    {_cedilla_row(seq, cursor)}")
    print()
    print(f"{DIM}[n/p] bout  [+/-] K  [[/]] kappa  [s] syllable feat  [r] refit  [q] quit{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PROTOTYPE bout HMM TUI")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prototype", type=Path, default=DEFAULT_PROTOTYPE)
    parser.add_argument("--trial-key", default=DEFAULT_TRIAL)
    parser.add_argument("--stream", default=DEFAULT_STREAM)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--n-states", type=int, default=5)
    parser.add_argument("--kappa", type=float, default=8.0)
    args = parser.parse_args()

    bouts = load_trial_bouts(
        args.manifest, stream=args.stream, seed=args.seed, trial_key=args.trial_key
    )
    if not bouts:
        raise SystemExit(f"No bouts for {args.trial_key} ({args.stream}/{args.seed})")

    cluster_lookup = load_cluster_lookup(args.prototype, stream=args.stream, seed=args.seed)
    include_syllable = False
    n_states = max(2, args.n_states)
    kappa = max(1.0, args.kappa)
    cursor = 0

    def refit(seq):
        model, decoded, ll = fit_sticky_hmm(
            seq.features, n_states=n_states, kappa=kappa, seed=42
        )
        return decoded, ll

    seq = build_trial_sequence(bouts, cluster_lookup=cluster_lookup, include_syllable=include_syllable)
    hmm_states, loglik = refit(seq)
    summary = summarize_decode(seq, hmm_states)

    while True:
        render(
            seq=seq,
            hmm_states=hmm_states,
            cursor=cursor,
            n_states=n_states,
            kappa=kappa,
            include_syllable=include_syllable,
            loglik=loglik,
            summary=summary,
        )
        key = _read_key()
        if key in ("q", "\x1b"):
            break
        if key == "n":
            cursor = min(cursor + 1, len(seq.bouts) - 1)
        elif key == "p":
            cursor = max(cursor - 1, 0)
        elif key == "+":
            n_states = min(n_states + 1, min(12, len(seq.bouts) - 1))
            hmm_states, loglik = refit(seq)
            summary = summarize_decode(seq, hmm_states)
        elif key == "-":
            n_states = max(2, n_states - 1)
            hmm_states, loglik = refit(seq)
            summary = summarize_decode(seq, hmm_states)
        elif key == "]":
            kappa = min(kappa * 1.25, 64.0)
            hmm_states, loglik = refit(seq)
            summary = summarize_decode(seq, hmm_states)
        elif key == "[":
            kappa = max(1.0, kappa / 1.25)
            hmm_states, loglik = refit(seq)
            for k, v in summarize_decode(seq, hmm_states).items():
                summary[k] = v
        elif key == "s":
            include_syllable = not include_syllable
            seq = build_trial_sequence(
                bouts, cluster_lookup=cluster_lookup, include_syllable=include_syllable
            )
            hmm_states, loglik = refit(seq)
            summary = summarize_decode(seq, hmm_states)
        elif key == "r":
            hmm_states, loglik = refit(seq)
            summary = summarize_decode(seq, hmm_states)


if __name__ == "__main__":
    main()
