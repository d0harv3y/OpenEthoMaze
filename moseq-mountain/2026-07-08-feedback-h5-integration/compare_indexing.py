"""Compare direct vs run-offset motor_fb lookup for legacy feedback table."""
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

TRACKING_H5 = Path(r"C:\Users\admin\Documents\work\sack\vast_results_legacy.h5")
TRIAL = "3245/S01/T01"


def main() -> None:
    with h5py.File(TRACKING_H5, "r") as h5:
        g = h5[TRIAL]
        run_row = int(g.attrs.get("trial_start_frame", 0) or 0)
        fb = g["feedback"]["table"]
        m = np.asarray(fb["motor_fb"], dtype=np.float64)

        # Absolute frames along run phase
        for abs_f in (278, 500, 1000, 3300, 3322, 3323, 3599):
            direct = float(m[abs_f]) if 0 <= abs_f < len(m) else float("nan")
            rel = abs_f - run_row
            offset = float(m[rel]) if 0 <= rel < len(m) else float("nan")
            print(f"abs={abs_f:4d}  direct[{abs_f}]={direct:8.3f}  offset[{rel}]={offset:8.3f}")


if __name__ == "__main__":
    main()
