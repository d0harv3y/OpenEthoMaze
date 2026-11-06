"""Batch-export SA-TVM H5 → npz for keypoint-MoSeq weekend fits."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from of_rear_classifier.export_sa_kpms import sa_h5_to_coordinates, write_recording_npz
from of_rear_classifier.sa_kpms_skeleton import SA_KPMS_BODY_PARTS


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--h5-dir", type=Path, required=True, help="Folder of *_superanimal_*.h5")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--likelihood-min", type=float, default=0.3)
    p.add_argument("--glob", type=str, default="*superanimal*.h5")
    args = p.parse_args(argv)

    paths = sorted(args.h5_dir.glob(args.glob))
    if not paths:
        print(f"no H5 under {args.h5_dir} matching {args.glob}", flush=True)
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for i, h5 in enumerate(paths, start=1):
        stem = h5.name.split("_superanimal", 1)[0]
        coords, conf, parts = sa_h5_to_coordinates(h5, likelihood_min=args.likelihood_min)
        out = args.out_dir / f"{stem}.npz"
        write_recording_npz(out, coords, conf, parts, recording_id=stem)
        manifest_rows.append(
            {
                "recording_id": stem,
                "h5": str(h5),
                "npz": str(out),
                "n_frames": int(coords.shape[0]),
                "n_keypoints": int(coords.shape[1]),
            }
        )
        print(f"[{i}/{len(paths)}] {stem} T={coords.shape[0]} K={coords.shape[1]} → {out.name}", flush=True)

    import pandas as pd

    man = args.out_dir / "manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(man, index=False)
    (args.out_dir / "body_parts.txt").write_text("\n".join(SA_KPMS_BODY_PARTS) + "\n", encoding="utf-8")
    print(f"wrote {man} ({len(manifest_rows)} recordings)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
