"""
Render a single trial video with overlay indicators (W, M, trial timer,
cumulative distance, cumulative time still).

Output filename is the original video name with '_overlay' suffix, written
under the path given by --out (directory or path with extension).

Usage:
    python scripts/render_overlay_video.py -a 2314 -s S01 -t T01 -o D:/overlays
    python scripts/render_overlay_video.py -a 2314 -s S01 -t T01 -o D:/overlays --max-seconds 60
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vast_pipeline.config import OUTPUT_H5
from vast_pipeline.storage.h5_db import TrialKey
from vast_pipeline.viz.video_overlay import render_overlay_video


def main():
    parser = argparse.ArgumentParser(
        description="Render trial video with W, M, timer, cumulative distance, time still"
    )
    parser.add_argument("--db", "-d", type=Path, default=None, help="Path to output H5 (default: config)")
    parser.add_argument("--animal", "-a", type=str, required=True, help="Animal ID")
    parser.add_argument("--phase", "-p", type=str, default="experimental", choices=["habituation", "experimental"])
    parser.add_argument("--session", "-s", type=str, required=True, help="Session (e.g. S01)")
    parser.add_argument("--trial", "-t", type=str, required=True, help="Trial (e.g. T01)")
    parser.add_argument(
        "--out", "-o", type=Path, required=True,
        help="Output path: directory (file named <original>_overlay.mp4) or path with extension",
    )
    parser.add_argument("--max-seconds", type=float, default=None, help="Cap output duration (seconds)")
    parser.add_argument("--contrast", type=float, default=2.0, help="Contrast scale (default 2.0)")
    parser.add_argument("--brightness", type=float, default=5.0, help="Brightness offset (default 5.0)")
    args = parser.parse_args()

    db_path = args.db or OUTPUT_H5
    key = TrialKey(animal_id=args.animal, phase=args.phase, session=args.session, trial=args.trial)

    written = render_overlay_video(
        db_path, key, args.out,
        max_seconds=args.max_seconds,
        contrast=args.contrast,
        brightness=args.brightness,
    )
    print(f"Wrote {written}")


if __name__ == "__main__":
    main()
    sys.exit(0)
