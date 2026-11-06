"""Syllable-bout labeler: video + bout table → labels for Goal B.

Uses matplotlib (OEM opencv is often built with GUI:NONE / headless).

Keys
----
1 Supported · 2 Unsupported · 3 Grooming · 0 / n None
a / d  previous / next bout · space play bout · s save · q quit

Bout CSV columns: bout_index, syllable_id, t0_frame, t1_frame [, label]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import matplotlib.pyplot as plt
import numpy as np

from of_rear_classifier.syllable_bouts import (
    bouts_to_sturman_intervals,
    load_bout_table,
    save_bout_table,
)

LABEL_KEYS = {
    "1": "Supported",
    "2": "Unsupported",
    "3": "Grooming",
    "0": "None",
    "n": "None",
}


def _read_frame(cap: cv2.VideoCapture, frame_idx: int) -> np.ndarray | None:
    cap.set(cv2.CAP_PROP_POS_FRAMES, float(frame_idx))
    ok, frame = cap.read()
    if not ok:
        return None
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--bouts", type=Path, required=True, help="CSV bout table")
    p.add_argument("--out", type=Path, default=None, help="default: overwrite --bouts")
    p.add_argument("--fps", type=float, default=None, help="for Sturman-interval export")
    p.add_argument("--export-intervals", type=Path, default=None, help="optional Sturman-like CSV")
    p.add_argument("--video-id", type=str, default=None)
    args = p.parse_args(argv)

    out_path = args.out or args.bouts
    df = load_bout_table(args.bouts)
    if df.empty:
        print("empty bout table", flush=True)
        return 1

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        print(f"cannot open video {args.video}", flush=True)
        return 1
    fps = float(args.fps) if args.fps else float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    i = 0
    dirty = False
    print(
        f"loaded {len(df)} bouts · video frames≈{n_frames} · fps={fps:.2f}\n"
        "focus the matplotlib window, then:\n"
        "  1 Supported · 2 Unsupported · 3 Grooming · 0/n None\n"
        "  a/d prev/next · space play · s save · q quit",
        flush=True,
    )

    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 7))
    fig.canvas.manager.set_window_title("of_rear syllable label")  # type: ignore[union-attr]
    im_artist = None
    status = {"key": None}

    def _on_key(event):
        if event.key is not None:
            status["key"] = event.key

    fig.canvas.mpl_connect("key_press_event", _on_key)

    def _show(frame: np.ndarray, title: str) -> None:
        nonlocal im_artist
        ax.clear()
        im_artist = ax.imshow(frame)
        ax.set_title(title)
        ax.axis("off")
        fig.canvas.draw_idle()
        plt.pause(0.001)

    while plt.fignum_exists(fig.number):
        i = int(np.clip(i, 0, len(df) - 1))
        row = df.iloc[i]
        t0, t1 = int(row["t0_frame"]), int(row["t1_frame"])
        lab = str(row.get("label", "") or "")
        title = (
            f"bout {i + 1}/{len(df)}  syll={int(row['syllable_id'])}  "
            f"frames {t0}-{t1}  label={lab or '(unset)'}"
        )
        frame = _read_frame(cap, t0)
        if frame is None:
            print(f"seek failed at frame {t0}", flush=True)
            break
        _show(frame, title)

        status["key"] = None
        while status["key"] is None and plt.fignum_exists(fig.number):
            plt.pause(0.05)
        if not plt.fignum_exists(fig.number):
            break
        key = status["key"]
        status["key"] = None

        if key in ("q", "escape"):
            break
        if key == "s":
            save_bout_table(df, out_path)
            dirty = False
            print(f"saved {out_path}", flush=True)
            if args.export_intervals is not None:
                vid = args.video_id or args.video.stem
                intervals = bouts_to_sturman_intervals(df, fps=fps, video_id=vid)
                intervals.to_csv(args.export_intervals, index=False)
                print(f"exported intervals {args.export_intervals} ({len(intervals)} rows)", flush=True)
            continue
        if key in ("d", "right"):
            i += 1
            continue
        if key in ("a", "left"):
            i -= 1
            continue
        if key == " ":
            for fidx in range(t0, t1 + 1):
                fr = _read_frame(cap, fidx)
                if fr is None:
                    break
                _show(fr, title + f"  play {fidx}/{t1}")
                plt.pause(1.0 / max(fps, 1.0))
                if status["key"] in ("q", "escape"):
                    break
            status["key"] = None
            continue
        if key in LABEL_KEYS:
            df.at[df.index[i], "label"] = LABEL_KEYS[key]
            dirty = True
            i += 1
            continue

    if dirty:
        save_bout_table(df, out_path)
        print(f"auto-saved {out_path}", flush=True)
    cap.release()
    plt.close("all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
