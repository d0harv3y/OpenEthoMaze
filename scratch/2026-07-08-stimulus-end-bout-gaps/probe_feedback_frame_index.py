"""Diagnose feedback vs xy frame_index alignment for one legacy trial."""
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

TRACKING_H5 = Path(r"C:\Users\admin\Documents\work\sack\vast_results_legacy.h5")
TRIAL = "3245/S01/T01"


def main() -> None:
    with h5py.File(TRACKING_H5, "r") as h5:
        g = h5[TRIAL]
        attrs = dict(g.attrs)
        print("trial attrs:")
        for k in ("trial_start_frame", "h5_n_frames", "h5_fps", "video_n_frames"):
            if k in attrs:
                print(f"  {k}: {attrs[k]}")

        xy = g["ambulation_metrics"]["spot"]["xy"][:]
        fb = g["feedback"]["table"][:]
        n_xy = len(xy)
        n_fb = len(fb)
        print(f"\nxy rows: {n_xy}")
        print(f"feedback rows: {n_fb}")
        print(f"gap xy-fb: {n_xy - n_fb}")

        fi_xy = np.asarray(xy["frame_index"], dtype=np.int64)
        fi_fb = np.asarray(fb["frame_index"], dtype=np.int64)
        print(f"\nxy frame_index: min={fi_xy.min()} max={fi_xy.max()}")
        print(f"fb frame_index: min={fi_fb.min()} max={fi_fb.max()}")

        ts_xy = [r.decode() if isinstance(r, (bytes, np.bytes_)) else str(r) for r in xy["trial_state"]]
        ts_fb = [r.decode() if isinstance(r, (bytes, np.bytes_)) else str(r) for r in fb["trial_state"]]
        from collections import Counter

        print("xy trial_state counts:", Counter(ts_xy))
        print("fb trial_state counts:", Counter(ts_fb))

        run_row = int(attrs.get("trial_start_frame", 0) or 0)
        print(f"\nassuming trial_start_frame/run_row = {run_row}")
        print(f"expected run length n_xy-run_row = {n_xy - run_row}")

        # Where does xy flip to run?
        run_rows_xy = [i for i, s in enumerate(ts_xy) if s.strip().lower() == "run"]
        if run_rows_xy:
            print(f"first xy run row: {run_rows_xy[0]} frame_index={fi_xy[run_rows_xy[0]]}")

        # Compare motor at absolute frame via offset vs direct index
        abs_frame = run_row + 100
        if abs_frame < n_xy:
            direct = float(fb["motor_fb"][abs_frame]) if abs_frame < n_fb else float("nan")
            offset = float(fb["motor_fb"][100]) if 100 < n_fb else float("nan")
            print(f"\n@ absolute video frame {abs_frame}:")
            print(f"  fb[motor_fb][{abs_frame}] (wrong direct): {direct}")
            print(f"  fb[motor_fb][{abs_frame - run_row}] (run-offset): {offset}")

        # Tail: last in-range absolute frame for feedback
        last_fb_idx = n_fb - 1
        abs_last = run_row + last_fb_idx
        print(f"\nlast feedback row index {last_fb_idx} -> absolute frame {abs_last}")
        print(f"last xy frame_index: {fi_xy[-1]}")
        print(f"kpMS would OOB for src >= {run_row + n_fb}")


if __name__ == "__main__":
    main()
