"""Smoke: SA-TVM H5 → 22-D skeleton (+ optional window) via thin ``dlc_h5`` import."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from of_rear_classifier.arena import load_floor_quad_vertices, point_in_polygon
from of_rear_classifier.parts_map import SA_TVM_PARTS
from of_rear_classifier.skeleton import N_FEATURES, skeleton_features, zscore_skeleton
from of_rear_classifier.window import DEFAULT_INTEGRATION_WINDOW, stack_centered, window_feature_dim


def _stem_from_h5(h5: Path) -> str:
    name = h5.name
    # Test 27_superanimal_….h5 → Test 27
    if "_superanimal" in name:
        return name.split("_superanimal", 1)[0]
    return h5.stem


def load_parts_xy(h5_path: Path, *, max_frames: int | None, individual: str = "animal0") -> dict[str, np.ndarray]:
    from maze.pipeline.open_field.dlc_h5 import bodypart_xy_likelihood, read_pose_table

    df = read_pose_table(h5_path)
    parts: dict[str, np.ndarray] = {}
    for name in SA_TVM_PARTS:
        xy, _lik = bodypart_xy_likelihood(df, name, individual=individual)
        if max_frames is not None:
            xy = xy[: max_frames]
        parts[name] = xy
    return parts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--h5", type=Path, required=True)
    p.add_argument("--quad-csv", type=Path, default=None, help="floor_quads.csv for P1/P2")
    p.add_argument("--video-stem", type=str, default=None)
    p.add_argument("--max-frames", type=int, default=300)
    p.add_argument("--integration-window", type=int, default=DEFAULT_INTEGRATION_WINDOW)
    args = p.parse_args(argv)

    parts = load_parts_xy(args.h5, max_frames=args.max_frames)
    t = next(iter(parts.values())).shape[0]

    in_nose = in_head = None
    if args.quad_csv is not None:
        stem = args.video_stem or _stem_from_h5(args.h5)
        verts = load_floor_quad_vertices(args.quad_csv, stem)
        in_nose = point_in_polygon(parts["nose"], verts)
        in_head = point_in_polygon(parts["head_midpoint"], verts)

    feat = skeleton_features(parts, in_arena_nose=in_nose, in_arena_head=in_head)
    feat_z = zscore_skeleton(feat)
    print(f"frames={t} features={feat.shape} z={feat_z.shape} n_feat={N_FEATURES}")

    w = args.integration_window
    if t >= 2 * w + 1:
        x, _ = stack_centered(feat_z, integration_window=w)
        print(f"window W={w} X={x.shape} expected_width={window_feature_dim(w)}")
    else:
        print(f"skip window: T={t} < 2W+1={2 * w + 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
