"""
Quick diagnostic: compare FPS from video metadata vs H5 timer0.

Samples trials across the dataset and prints FPS comparisons.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("cv2 not available, cannot read video FPS")
    sys.exit(1)

from vast_pipeline.config import DATA_DIR
from vast_pipeline.io.file_discovery import discover_trials
from vast_pipeline.io.input_h5_loader import load_trial_data


def main():
    print(f"Discovering trials from {DATA_DIR}...")
    result = discover_trials(DATA_DIR)

    # Pick trials that have both video and H5 data
    candidates = [
        t for t in result.trials
        if t.video_path and t.video_path.exists()
    ]
    print(f"\n{len(candidates)} trials with videos available")

    # Sample up to 50 spread across the dataset
    step = max(1, len(candidates) // 50)
    sample = candidates[::step][:50]

    print(f"Sampling {len(sample)} trials...\n")
    print(f"{'trial_key':<30} {'h5_frames':>10} {'h5_dur_s':>10} {'h5_fps':>8} "
          f"{'vid_frames':>10} {'vid_dur_s':>10} {'vid_fps':>8} {'fps_diff':>9}")
    print("-" * 120)

    h5_fps_list = []
    vid_fps_list = []

    for trial in sample:
        h5_frames = ""
        h5_dur = ""
        h5_fps_str = ""
        h5_fps_val = None

        vid_frames = ""
        vid_dur = ""
        vid_fps_str = ""
        vid_fps_val = None

        # H5 data (use h5_session to account for session renumbering)
        try:
            data = load_trial_data(
                trial.input_h5_path,
                trial.animal_id,
                trial.h5_session,
                trial.trial,
            )
            n = data.n_frames
            dur = data.duration_s
            h5_frames = str(n)
            h5_dur = f"{dur:.2f}"
            if dur > 0 and n > 1:
                fps = (n - 1) / dur
                h5_fps_str = f"{fps:.2f}"
                h5_fps_val = fps
                h5_fps_list.append(fps)
        except Exception as e:
            h5_frames = f"err"

        # Video metadata
        try:
            cap = cv2.VideoCapture(str(trial.video_path))
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.release()

                vid_fps_val = fps
                vid_fps_str = f"{fps:.2f}"
                vid_frames = str(fc)
                if fps > 0 and fc > 0:
                    vid_dur = f"{fc / fps:.2f}"
                vid_fps_list.append(fps)
        except Exception:
            vid_frames = "err"

        # Difference
        diff_str = ""
        if h5_fps_val is not None and vid_fps_val is not None:
            diff_str = f"{vid_fps_val - h5_fps_val:+.2f}"

        key = f"{trial.animal_id}/{trial.phase[:3]}/{trial.session}/{trial.trial}"
        print(f"{key:<30} {h5_frames:>10} {h5_dur:>10} {h5_fps_str:>8} "
              f"{vid_frames:>10} {vid_dur:>10} {vid_fps_str:>8} {diff_str:>9}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if h5_fps_list:
        arr = np.array(h5_fps_list)
        print(f"\nH5 FPS (from timer0):")
        print(f"  mean={arr.mean():.3f}  std={arr.std():.3f}  "
              f"min={arr.min():.3f}  max={arr.max():.3f}")
        print(f"  unique values: {sorted(set(f'{x:.2f}' for x in arr))}")

    if vid_fps_list:
        arr = np.array(vid_fps_list)
        print(f"\nVideo FPS (from metadata):")
        print(f"  mean={arr.mean():.3f}  std={arr.std():.3f}  "
              f"min={arr.min():.3f}  max={arr.max():.3f}")
        print(f"  unique values: {sorted(set(f'{x:.2f}' for x in arr))}")


if __name__ == "__main__":
    main()
