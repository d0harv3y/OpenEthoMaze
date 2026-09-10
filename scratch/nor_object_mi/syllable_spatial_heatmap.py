"""Spatial time-in-syllable heatmaps (QC-style) for NOR simpler-first.

Per grain (phase × condition × sex × condition): blank canvas + arena-box outline,
dwell seconds accumulated from spot xy when each kpMS model labels a syllable,
all models overlaid. Color = HDBSCAN ``cluster_id``; opacity ∝ dwell time.

Novel-object sessions where fam sits on the right (``nvl_nearest_hist_locus == 'a'``)
are rotated 180° about the arena center so **fam is always on the left**.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import h5py
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.bout_kinematics import (  # noqa: E402
    CONDITIONS,
    SESSIONS,
    discover_paramscan_models,
)
from nor_object_mi.fam_nvl import fam_nvl_map_for_session  # noqa: E402
from nor_object_mi.join_keys import (  # noqa: E402
    JoinedSession,
    filter_cohort,
    iter_nor_sessions,
    parse_kpms_group,
)
from nor_object_mi.pseudo_loci import loci_for_animal_phase  # noqa: E402
from nor_object_mi.spot_xy import object_centers_px, spot_xy_px  # noqa: E402
from nor_object_mi._pub_style import CONDITION_COLOR, CONDITION_ORDER  # noqa: E402
from nor_object_mi.condition_argmax_grid import kpms_key_to_mp4  # noqa: E402

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

SEX_ORDER: tuple[str, ...] = ("F", "M")
NOISE_CLUSTER = -1
DEFAULT_FRAME_STRIDE = 30
DEFAULT_BLUR_SIGMA = 3.0
DEFAULT_OVERLAY_MAX_ALPHA = 0.88
DEFAULT_CANVAS_BGR = (0, 0, 0)
ARENA_OUTLINE_BGR = (150, 150, 150)
ARENA_OUTLINE_THICKNESS = 1
LOCUS_RADIUS_PX = 20
LEGEND_COLS = 14


@dataclass(frozen=True)
class GrainKey:
    session: str
    trial: str
    sex: str
    condition: str

    def slug(self) -> str:
        return f"{self.session}__{self.trial}__{self.sex}__{self.condition}"


@dataclass(frozen=True)
class TxOverlayGrainKey:
    """phase × condition × sex with all tx pooled; color = treatment stratum."""

    session: str
    trial: str
    sex: str

    def slug(self) -> str:
        return f"{self.session}__{self.trial}__{self.sex}__all_tx"


@dataclass(frozen=True)
class SessionSpec:
    animal_id: str
    raw_session: str
    session: str
    trial: str
    sex: str
    condition: str
    rotate_180: bool
    nvl_side: str
    kpms_by_model: dict[str, str]


def arena_bbox_px(session: h5py.Group) -> np.ndarray:
    """Axis-aligned arena box ``[x0, y0, x1, y1]`` in session pixel coords."""
    if "objects" not in session:
        raise KeyError("arena bbox missing")
    objs = session["objects"]
    if "arena" not in objs or "bbox" not in objs["arena"]:
        raise KeyError("arena bbox missing")
    bb = np.asarray(objs["arena"]["bbox"][()], dtype=np.float64).ravel()[:4]
    if bb.size < 4 or not np.all(np.isfinite(bb)):
        raise KeyError("arena bbox invalid")
    return bb.copy()


def arena_center_px(session: h5py.Group) -> tuple[float, float]:
    if "objects" in session:
        objs = session["objects"]
        if "arena" in objs and "center" in objs["arena"]:
            c = np.asarray(objs["arena"]["center"][()], dtype=np.float64).ravel()[:2]
            return float(c[0]), float(c[1])
    bb = arena_bbox_px(session)
    return float((bb[0] + bb[2]) / 2.0), float((bb[1] + bb[3]) / 2.0)


def rotate180_xy(
    x: np.ndarray,
    y: np.ndarray,
    *,
    cx: float,
    cy: float,
) -> tuple[np.ndarray, np.ndarray]:
    return (2.0 * cx - x), (2.0 * cy - y)


@dataclass(frozen=True)
class LocusMarker:
    x: int
    y: int
    label: str


def rotate180_point(pt: np.ndarray, cx: float, cy: float) -> np.ndarray:
    p = np.asarray(pt, dtype=np.float64).ravel()[:2]
    return np.array([2.0 * cx - p[0], 2.0 * cy - p[1]], dtype=np.float64)


def _session_scale_to_canvas(
    kpms_key: str,
    video_root: Path,
    canonical_hw: tuple[int, int],
) -> tuple[float, float]:
    ch, cw = canonical_hw
    mp4 = kpms_key_to_mp4(kpms_key, video_root)
    try:
        vid_h, vid_w = video_frame_size(mp4)
    except (OSError, ValueError):
        return 1.0, 1.0
    return (cw / float(vid_w) if vid_w > 0 else 1.0, ch / float(vid_h) if vid_h > 0 else 1.0)


def loci_markers_for_grain(
    nor_h5: h5py.File,
    sessions: list[SessionSpec],
    *,
    trial: str,
    canonical_hw: tuple[int, int],
    video_root: Path,
) -> list[LocusMarker]:
    """Mean locus positions after alignment; labels by role / condition."""
    left_pts: list[np.ndarray] = []
    right_pts: list[np.ndarray] = []
    for spec in sessions:
        if spec.animal_id not in nor_h5 or spec.raw_session not in nor_h5[spec.animal_id]:
            continue
        sg = nor_h5[spec.animal_id][spec.raw_session]
        loci = loci_for_animal_phase(nor_h5, spec.animal_id, spec.session)
        if loci is None:
            continue
        la = np.asarray(loci[0], dtype=np.float64)
        lb = np.asarray(loci[1], dtype=np.float64)
        if trial == "nvl_obj" and spec.nvl_side in {"a", "b"}:
            # Role before rotation: nvl on hist A → fam at B; else fam at A.
            if spec.nvl_side == "a":
                fam_pt, nvl_pt = lb.copy(), la.copy()
            else:
                fam_pt, nvl_pt = la.copy(), lb.copy()
            if spec.rotate_180:
                cx, cy = arena_center_px(sg)
                fam_pt = rotate180_point(fam_pt, cx, cy)
                nvl_pt = rotate180_point(nvl_pt, cx, cy)
            left_pt, right_pt = fam_pt, nvl_pt
        elif trial == "id_obj":
            # Hist locus 0/1 (lower-x first); no rot180 — id_0 stays left.
            if spec.rotate_180:
                cx, cy = arena_center_px(sg)
                la = rotate180_point(la, cx, cy)
                lb = rotate180_point(lb, cx, cy)
            left_pt, right_pt = la, lb
        else:
            if spec.rotate_180:
                cx, cy = arena_center_px(sg)
                la = rotate180_point(la, cx, cy)
                lb = rotate180_point(lb, cx, cy)
            left_pt, right_pt = la, lb
        kpms_key = next(iter(spec.kpms_by_model.values()))
        sx, sy = _session_scale_to_canvas(kpms_key, video_root, canonical_hw)
        left_pts.append(left_pt * np.array([sx, sy]))
        right_pts.append(right_pt * np.array([sx, sy]))

    if not left_pts:
        return []
    if trial == "nvl_obj":
        labels = ("fam", "nvl")
    elif trial == "id_obj":
        labels = ("id_0", "id_1")
    elif trial == "no_obj":
        labels = ("no_0", "no_1")
    else:
        labels = ("no", "no")
    ml = np.mean(np.stack(left_pts, axis=0), axis=0)
    mr = np.mean(np.stack(right_pts, axis=0), axis=0)
    sep = float(np.linalg.norm(ml - mr))
    if trial in {"nvl_obj", "id_obj", "no_obj"} and sep < 40.0:
        raise RuntimeError(
            f"{trial} loci collapsed (sep={sep:.1f}px); "
            "left/right means must stay distinct"
        )
    return [
        LocusMarker(int(round(ml[0])), int(round(ml[1])), labels[0]),
        LocusMarker(int(round(mr[0])), int(round(mr[1])), labels[1]),
    ]


def mean_arena_bbox_for_grain(
    nor_h5: h5py.File,
    sessions: list[SessionSpec],
    *,
    canonical_hw: tuple[int, int],
    video_root: Path,
) -> np.ndarray | None:
    """Mean scaled arena AABB on the canonical canvas (rot180 leaves AABB unchanged)."""
    boxes: list[np.ndarray] = []
    for spec in sessions:
        if spec.animal_id not in nor_h5 or spec.raw_session not in nor_h5[spec.animal_id]:
            continue
        sg = nor_h5[spec.animal_id][spec.raw_session]
        try:
            bb = arena_bbox_px(sg)
        except KeyError:
            continue
        kpms_key = next(iter(spec.kpms_by_model.values()))
        sx, sy = _session_scale_to_canvas(kpms_key, video_root, canonical_hw)
        boxes.append(
            np.array(
                [bb[0] * sx, bb[1] * sy, bb[2] * sx, bb[3] * sy],
                dtype=np.float64,
            )
        )
    if not boxes:
        return None
    return np.mean(np.stack(boxes, axis=0), axis=0)


def blank_canvas(
    canonical_hw: tuple[int, int],
    *,
    bgr: tuple[int, int, int] = DEFAULT_CANVAS_BGR,
) -> np.ndarray:
    h, w = canonical_hw
    return np.full((h, w, 3), bgr, dtype=np.uint8)


def draw_arena_outline(
    img_bgr: np.ndarray,
    bbox_xyxy: np.ndarray | None,
    *,
    color_bgr: tuple[int, int, int] = ARENA_OUTLINE_BGR,
    thickness: int = ARENA_OUTLINE_THICKNESS,
) -> None:
    if not HAS_CV2 or bbox_xyxy is None:
        return
    x0, y0, x1, y1 = [int(round(float(v))) for v in np.asarray(bbox_xyxy).ravel()[:4]]
    cv2.rectangle(img_bgr, (x0, y0), (x1, y1), color_bgr, thickness, lineType=cv2.LINE_AA)


def draw_loci_markers(
    img_bgr: np.ndarray,
    markers: list[LocusMarker],
    *,
    radius: int = LOCUS_RADIUS_PX,
) -> None:
    if not HAS_CV2 or not markers:
        return
    out = img_bgr
    for m in markers:
        center = (int(m.x), int(m.y))
        cv2.circle(out, center, radius, (255, 255, 255), 2, lineType=cv2.LINE_AA)
        cv2.circle(out, center, radius, (30, 30, 30), 1, lineType=cv2.LINE_AA)
        cv2.putText(
            out,
            m.label,
            (center[0] - 14, center[1] - radius - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            out,
            m.label,
            (center[0] - 14, center[1] - radius - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )


def _put_outlined_text(
    img_bgr: np.ndarray,
    text: str,
    org: tuple[int, int],
    *,
    scale: float = 0.55,
) -> None:
    if not HAS_CV2:
        return
    cv2.putText(
        img_bgr,
        text,
        org,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img_bgr,
        text,
        org,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (20, 20, 20),
        1,
        cv2.LINE_AA,
    )


def draw_rotation_notation(
    img_bgr: np.ndarray,
    *,
    n_rotated: int,
    n_sessions: int,
) -> None:
    """Upper-left: sessions rotated ~180° / grain n (fam-left alignment)."""
    _put_outlined_text(img_bgr, f"rot180: {n_rotated}/{n_sessions}", (8, 22))


def draw_condition_notation(img_bgr: np.ndarray, condition: str) -> None:
    """Upper-right: treatment stratum for this grain."""
    if not HAS_CV2:
        return
    text = str(condition)
    scale = 0.55
    (tw, _th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x = max(8, int(img_bgr.shape[1]) - tw - 8)
    _put_outlined_text(img_bgr, text, (x, 22), scale=scale)


def rotate180_bgr(img: np.ndarray) -> np.ndarray:
    if not HAS_CV2:
        raise RuntimeError("opencv required")
    return cv2.rotate(img, cv2.ROTATE_180)


def nvl_nearest_hist_locus(
    nor_h5: h5py.File,
    *,
    animal_id: str,
    session: str,
    raw_session: str,
    trial: str,
) -> str:
    """Return ``a`` | ``b`` | ```` for which historical locus is nearer the novel center."""
    if trial != "nvl_obj":
        return ""
    if animal_id not in nor_h5 or raw_session not in nor_h5[animal_id]:
        return ""
    sg = nor_h5[animal_id][raw_session]
    loci = loci_for_animal_phase(nor_h5, animal_id, session)
    if loci is None:
        return ""
    role_map = fam_nvl_map_for_session(nor_h5, animal_id, raw_session)
    if not role_map:
        return ""
    centers = object_centers_px(sg)
    nvl_key = next((k for k, v in role_map.items() if v == "nvl"), None)
    if nvl_key is None or nvl_key not in centers:
        return ""
    nvl_c = centers[nvl_key]
    d_a = float(np.sum((nvl_c - loci[0]) ** 2))
    d_b = float(np.sum((nvl_c - loci[1]) ** 2))
    return "a" if d_a <= d_b else "b"


def needs_novel_alignment(nvl_side: str) -> bool:
    """True when fam is on the right (nvl on hist A) — rotate 180 so fam sits left."""
    return nvl_side == "a"


def build_kpms_index(
    ensemble_root: Path,
    models: list[str],
) -> dict[tuple[str, str], dict[str, str]]:
    """``(animal_id, raw_session)`` → ``{model: kpms_key}``."""
    out: dict[tuple[str, str], dict[str, str]] = {}
    for model in models:
        results = ensemble_root / model / "results.h5"
        if not results.is_file():
            continue
        with h5py.File(results, "r") as f:
            for key in f.keys():
                try:
                    animal_id, raw_session = parse_kpms_group(str(key))
                except ValueError:
                    continue
                out.setdefault((animal_id, raw_session), {})[model] = str(key)
    return out


def iter_grain_sessions(
    nor_h5: h5py.File,
    kpms_index: dict[tuple[str, str], dict[str, str]],
    grain: GrainKey | TxOverlayGrainKey,
) -> Iterator[SessionSpec]:
    for js in iter_nor_sessions(nor_h5, kept_ids=set(filter_cohort(nor_h5)["kept_ids"])):
        if js.session != grain.session:
            continue
        if js.trial != grain.trial:
            continue
        if js.sex != grain.sex:
            continue
        if isinstance(grain, GrainKey) and js.condition != grain.condition:
            continue
        if js.trial not in CONDITIONS:
            continue
        key = (js.animal_id, js.raw_session)
        kpms_by_model = kpms_index.get(key, {})
        if not kpms_by_model:
            continue
        nvl_side = nvl_nearest_hist_locus(
            nor_h5,
            animal_id=js.animal_id,
            session=js.session,
            raw_session=js.raw_session,
            trial=js.trial,
        )
        rotate = js.trial == "nvl_obj" and needs_novel_alignment(nvl_side)
        yield SessionSpec(
            animal_id=js.animal_id,
            raw_session=js.raw_session,
            session=js.session,
            trial=js.trial,
            sex=js.sex,
            condition=js.condition,
            rotate_180=rotate,
            nvl_side=nvl_side,
            kpms_by_model=kpms_by_model,
        )


def build_cluster_lookup(proto: pd.DataFrame) -> dict[tuple[str, int], int]:
    need = {"model", "raw_syllable_id", "cluster_id"}
    if not need.issubset(proto.columns):
        raise KeyError(f"prototypes missing {sorted(need - set(proto.columns))}")
    out: dict[tuple[str, int], int] = {}
    for row in proto.itertuples(index=False):
        out[(str(row.model), int(row.raw_syllable_id))] = int(row.cluster_id)
    return out


def video_frame_size(mp4: Path) -> tuple[int, int]:
    if not HAS_CV2:
        raise RuntimeError("opencv required")
    cap = cv2.VideoCapture(str(mp4))
    if not cap.isOpened():
        raise OSError(f"cannot open video: {mp4}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if w <= 0 or h <= 0:
        raise ValueError(f"invalid video size for {mp4}")
    return h, w


def _read_video_frames_strided(
    mp4: Path,
    *,
    frame_stride: int,
    rotate_180: bool,
    out_hw: tuple[int, int] | None = None,
) -> list[np.ndarray]:
    if not HAS_CV2:
        raise RuntimeError("opencv required")
    cap = cv2.VideoCapture(str(mp4))
    if not cap.isOpened():
        raise OSError(f"cannot open video: {mp4}")
    frames: list[np.ndarray] = []
    idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % frame_stride == 0:
                bgr = frame
                if rotate_180:
                    bgr = rotate180_bgr(bgr)
                if out_hw is not None and (bgr.shape[0], bgr.shape[1]) != out_hw:
                    bgr = cv2.resize(bgr, (out_hw[1], out_hw[0]), interpolation=cv2.INTER_AREA)
                frames.append(bgr)
            idx += 1
    finally:
        cap.release()
    return frames


def median_background(
    sessions: list[SessionSpec],
    *,
    video_root: Path,
    frame_stride: int,
    canonical_hw: tuple[int, int],
) -> tuple[np.ndarray, list[str]]:
    """Return BGR uint8 median image and list of sessions used."""
    stacks: list[np.ndarray] = []
    used: list[str] = []
    for spec in sessions:
        any_key = next(iter(spec.kpms_by_model.values()))
        mp4 = kpms_key_to_mp4(any_key, video_root)
        if not mp4.is_file():
            continue
        frames = _read_video_frames_strided(
            mp4,
            frame_stride=frame_stride,
            rotate_180=spec.rotate_180,
            out_hw=canonical_hw,
        )
        if not frames:
            continue
        stacks.append(np.median(np.stack(frames, axis=0), axis=0).astype(np.float32))
        used.append(f"{spec.animal_id}/{spec.raw_session}")
    if not stacks:
        raise RuntimeError("no video frames for median background")
    med = np.median(np.stack(stacks, axis=0), axis=0).astype(np.uint8)
    return med, used


def _blur_grid(grid: np.ndarray, sigma: float) -> np.ndarray:
    if not HAS_CV2 or sigma <= 0:
        return grid
    return cv2.GaussianBlur(grid, (0, 0), sigmaX=float(sigma), sigmaY=float(sigma))


def resolve_canonical_hw(
    sessions: list[SessionSpec],
    video_root: Path,
) -> tuple[int, int]:
    for spec in sessions:
        any_key = next(iter(spec.kpms_by_model.values()))
        mp4 = kpms_key_to_mp4(any_key, video_root)
        if mp4.is_file():
            return video_frame_size(mp4)
    raise RuntimeError("no readable video to set canonical canvas size")


def accumulate_cluster_dwell(
    nor_h5: h5py.File,
    ensemble_root: Path,
    sessions: list[SessionSpec],
    models: list[str],
    cluster_lookup: dict[tuple[str, int], int],
    *,
    video_root: Path,
    canonical_hw: tuple[int, int],
    frame_stride: int = 1,
    blur_sigma: float = DEFAULT_BLUR_SIGMA,
    keep_clusters: frozenset[int] | None = None,
    progress_every_s: float = 30.0,
) -> tuple[dict[int, np.ndarray], dict[str, object]]:
    """Sum dwell seconds per cluster on the canonical video pixel grid.

    If ``keep_clusters`` is set, only those HDBSCAN ids accumulate (other
    syllables and noise are skipped — not dumped into noise).
    """
    if not sessions:
        raise ValueError("no sessions")
    ch, cw = canonical_hw
    if keep_clusters is not None:
        dwell: dict[int, np.ndarray] = {
            int(c): np.zeros((ch, cw), dtype=np.float32) for c in sorted(keep_clusters)
        }
    else:
        dwell = {NOISE_CLUSTER: np.zeros((ch, cw), dtype=np.float32)}

    fps_default = 30.0
    n_model_pass = 0
    t0 = time.monotonic()
    last_log = t0
    stats: dict[str, object] = {
        "n_sessions": len(sessions),
        "n_models": len(models),
        "frame_stride": frame_stride,
        "blur_sigma": blur_sigma,
        "keep_clusters": (
            [int(c) for c in sorted(keep_clusters)] if keep_clusters is not None else None
        ),
    }

    for model in models:
        results_path = ensemble_root / model / "results.h5"
        if not results_path.is_file():
            continue
        with h5py.File(results_path, "r") as kpms_h5:
            for spec in sessions:
                kpms_key = spec.kpms_by_model.get(model)
                if not kpms_key or kpms_key not in kpms_h5:
                    continue
                sg = nor_h5[spec.animal_id][spec.raw_session]
                x_px, y_px, valid = spot_xy_px(sg["sleap_data"])
                mp4 = kpms_key_to_mp4(kpms_key, video_root)
                try:
                    vid_h, vid_w = video_frame_size(mp4)
                except (OSError, ValueError):
                    vid_h, vid_w = canonical_hw
                sx = canonical_hw[1] / float(vid_w) if vid_w > 0 else 1.0
                sy = canonical_hw[0] / float(vid_h) if vid_h > 0 else 1.0
                syll = np.asarray(kpms_h5[kpms_key]["syllable"][:], dtype=np.int64)
                n = min(len(syll), len(valid))
                syll = syll[:n]
                valid = valid[:n]
                x_px = x_px[:n]
                y_px = y_px[:n]
                if spec.rotate_180:
                    cx, cy = arena_center_px(sg)
                    x_px, y_px = rotate180_xy(x_px, y_px, cx=cx, cy=cy)
                fps = float(sg.attrs.get("video_fps", fps_default) or fps_default)
                dt = float(frame_stride) / fps if fps > 0 else float(frame_stride) / fps_default

                for i in range(0, n, frame_stride):
                    if not valid[i]:
                        continue
                    xf = float(x_px[i]) * sx
                    yf = float(y_px[i]) * sy
                    if not (np.isfinite(xf) and np.isfinite(yf)):
                        continue
                    xi = int(round(xf))
                    yi = int(round(yf))
                    if xi < 0 or yi < 0 or xi >= cw or yi >= ch:
                        continue
                    sid = int(syll[i])
                    cid = cluster_lookup.get((model, sid), NOISE_CLUSTER)
                    if keep_clusters is not None and cid not in keep_clusters:
                        continue
                    if cid not in dwell:
                        dwell[cid] = np.zeros((ch, cw), dtype=np.float32)
                    dwell[cid][yi, xi] += dt

        n_model_pass += 1
        now = time.monotonic()
        if now - last_log >= progress_every_s:
            print(
                f"  dwell: model {n_model_pass}/{len(models)} "
                f"({model}) elapsed={now - t0:.0f}s",
                flush=True,
            )
            last_log = now

    if not dwell:
        raise RuntimeError("no dwell accumulated")

    if blur_sigma > 0:
        for cid in list(dwell.keys()):
            dwell[cid] = _blur_grid(dwell[cid], blur_sigma)

    stats["grid_h"] = int(ch)
    stats["grid_w"] = int(cw)
    stats["n_clusters_with_mass"] = int(sum(1 for g in dwell.values() if float(g.sum()) > 0))
    stats["total_dwell_s"] = float(sum(float(g.sum()) for g in dwell.values()))
    return dwell, stats


def accumulate_condition_dwell(
    nor_h5: h5py.File,
    ensemble_root: Path,
    sessions: list[SessionSpec],
    models: list[str],
    cluster_lookup: dict[tuple[str, int], int],
    *,
    video_root: Path,
    canonical_hw: tuple[int, int],
    frame_stride: int = 1,
    blur_sigma: float = DEFAULT_BLUR_SIGMA,
    keep_clusters: frozenset[int] | None = None,
    progress_every_s: float = 30.0,
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    """Sum cluster-filtered dwell seconds per tx on the canonical pixel grid."""
    if not sessions:
        raise ValueError("no sessions")
    ch, cw = canonical_hw
    dwell: dict[str, np.ndarray] = {condition: np.zeros((ch, cw), dtype=np.float32) for condition in CONDITION_ORDER}

    fps_default = 30.0
    n_model_pass = 0
    t0 = time.monotonic()
    last_log = t0
    stats: dict[str, object] = {
        "n_sessions": len(sessions),
        "n_models": len(models),
        "frame_stride": frame_stride,
        "blur_sigma": blur_sigma,
        "keep_clusters": (
            [int(c) for c in sorted(keep_clusters)] if keep_clusters is not None else None
        ),
        "color_by": "condition",
    }

    for model in models:
        results_path = ensemble_root / model / "results.h5"
        if not results_path.is_file():
            continue
        with h5py.File(results_path, "r") as kpms_h5:
            for spec in sessions:
                kpms_key = spec.kpms_by_model.get(model)
                if not kpms_key or kpms_key not in kpms_h5:
                    continue
                condition = str(spec.condition)
                if condition not in dwell:
                    continue
                sg = nor_h5[spec.animal_id][spec.raw_session]
                x_px, y_px, valid = spot_xy_px(sg["sleap_data"])
                mp4 = kpms_key_to_mp4(kpms_key, video_root)
                try:
                    vid_h, vid_w = video_frame_size(mp4)
                except (OSError, ValueError):
                    vid_h, vid_w = canonical_hw
                sx = canonical_hw[1] / float(vid_w) if vid_w > 0 else 1.0
                sy = canonical_hw[0] / float(vid_h) if vid_h > 0 else 1.0
                syll = np.asarray(kpms_h5[kpms_key]["syllable"][:], dtype=np.int64)
                n = min(len(syll), len(valid))
                syll = syll[:n]
                valid = valid[:n]
                x_px = x_px[:n]
                y_px = y_px[:n]
                if spec.rotate_180:
                    cx, cy = arena_center_px(sg)
                    x_px, y_px = rotate180_xy(x_px, y_px, cx=cx, cy=cy)
                fps = float(sg.attrs.get("video_fps", fps_default) or fps_default)
                dt = float(frame_stride) / fps if fps > 0 else float(frame_stride) / fps_default

                for i in range(0, n, frame_stride):
                    if not valid[i]:
                        continue
                    sid = int(syll[i])
                    cid = cluster_lookup.get((model, sid), NOISE_CLUSTER)
                    if keep_clusters is not None and cid not in keep_clusters:
                        continue
                    xf = float(x_px[i]) * sx
                    yf = float(y_px[i]) * sy
                    if not (np.isfinite(xf) and np.isfinite(yf)):
                        continue
                    xi = int(round(xf))
                    yi = int(round(yf))
                    if xi < 0 or yi < 0 or xi >= cw or yi >= ch:
                        continue
                    dwell[condition][yi, xi] += dt

        n_model_pass += 1
        now = time.monotonic()
        if now - last_log >= progress_every_s:
            print(
                f"  dwell: model {n_model_pass}/{len(models)} "
                f"({model}) elapsed={now - t0:.0f}s",
                flush=True,
            )
            last_log = now

    if blur_sigma > 0:
        for condition in list(dwell.keys()):
            dwell[condition] = _blur_grid(dwell[condition], blur_sigma)

    stats["grid_h"] = int(ch)
    stats["grid_w"] = int(cw)
    stats["n_condition_with_mass"] = int(sum(1 for g in dwell.values() if float(g.sum()) > 0))
    stats["total_dwell_s"] = float(sum(float(g.sum()) for g in dwell.values()))
    stats["dwell_s_by_tx"] = {condition: float(dwell[condition].sum()) for condition in CONDITION_ORDER}
    return dwell, stats


def hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    h = str(hex_color).lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (b, g, r)


def tx_colors_bgr() -> dict[str, tuple[int, int, int]]:
    return {condition: hex_to_bgr(CONDITION_COLOR[condition]) for condition in CONDITION_ORDER}


def cluster_colors_bgr(
    cluster_ids: list[int],
    lookup_rgba: dict[int, tuple[float, float, float, float]],
) -> dict[int, tuple[int, int, int]]:
    out: dict[int, tuple[int, int, int]] = {}
    for cid in cluster_ids:
        r, g, b, _a = lookup_rgba.get(cid, lookup_rgba.get(NOISE_CLUSTER, (0.78, 0.78, 0.78, 1.0)))
        out[cid] = (int(round(b * 255)), int(round(g * 255)), int(round(r * 255)))
    return out


def composite_dwell_overlay(
    background_bgr: np.ndarray,
    dwell_by_cluster: dict[object, np.ndarray],
    colors_bgr: dict[object, tuple[int, int, int]],
    *,
    vmax_s: float | None = None,
    max_alpha: float = DEFAULT_OVERLAY_MAX_ALPHA,
) -> np.ndarray:
    """Per-pixel weighted cluster-color mix; opacity from total dwell (avoids white wash)."""
    if not HAS_CV2:
        raise RuntimeError("opencv required")
    h, w = background_bgr.shape[:2]
    base = background_bgr.astype(np.float32)
    color_sum = np.zeros((h, w, 3), dtype=np.float32)
    total = np.zeros((h, w), dtype=np.float32)

    for cid, grid in dwell_by_cluster.items():
        if grid.shape[0] != h or grid.shape[1] != w:
            grid = cv2.resize(grid, (w, h), interpolation=cv2.INTER_LINEAR)
        g = grid.astype(np.float32)
        if float(g.sum()) <= 0:
            continue
        bgr = colors_bgr.get(cid, (200, 200, 200))
        for ch in range(3):
            color_sum[:, :, ch] += g * float(bgr[ch])
        total += g

    if vmax_s is None or vmax_s <= 0:
        pos = total[total > 0]
        vmax_s = float(np.percentile(pos, 95)) if pos.size else 1.0
        vmax_s = max(vmax_s, 1e-6)

    mixed = np.zeros_like(color_sum)
    mask = total > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        for ch in range(3):
            np.divide(
                color_sum[:, :, ch],
                total,
                out=mixed[:, :, ch],
                where=mask,
            )

    alpha = np.clip(total / vmax_s, 0.0, max_alpha)[:, :, np.newaxis]
    out = base * (1.0 - alpha) + mixed * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def write_shared_cluster_legend(
    path: Path,
    cluster_ids: list[int],
    colors_bgr: dict[int, tuple[int, int, int]],
    *,
    include_noise: bool = True,
) -> None:
    """One wrapped legend for all figures (cluster_id swatches + optional noise)."""
    import matplotlib.pyplot as plt

    ids = list(cluster_ids)
    if include_noise and NOISE_CLUSTER not in ids:
        ids = ids + [NOISE_CLUSTER]
    n = len(ids)
    cols = LEGEND_COLS
    rows = int(np.ceil(n / cols))
    fig_w = min(14.0, cols * 0.95)
    fig_h = max(1.2, rows * 0.42 + 0.35)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.axis("off")
    for i, cid in enumerate(ids):
        row = rows - 1 - (i // cols)
        col = i % cols
        b, g, r = colors_bgr.get(cid, (180, 180, 180))
        ax.add_patch(plt.Rectangle((col + 0.08, row + 0.12), 0.35, 0.55, color=(r / 255, g / 255, b / 255)))
        lab = "noise" if cid == NOISE_CLUSTER else str(cid)
        ax.text(col + 0.5, row + 0.4, lab, ha="left", va="center", fontsize=7)
    ax.set_title("cluster_id (HDBSCAN turbo)", fontsize=9, loc="left")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def write_condition_legend(path: Path) -> None:
    """Shared tx swatch legend (violin CONDITION_COLOR: green / orange / purple)."""
    import matplotlib.pyplot as plt

    colors = tx_colors_bgr()
    fig, ax = plt.subplots(figsize=(3.2, 0.55))
    ax.set_xlim(0, len(CONDITION_ORDER))
    ax.set_ylim(0, 1)
    ax.axis("off")
    for i, tx in enumerate(CONDITION_ORDER):
        b, g, r = colors[condition]
        ax.add_patch(
            plt.Rectangle((i + 0.08, 0.25), 0.35, 0.5, color=(r / 255, g / 255, b / 255))
        )
        ax.text(i + 0.5, 0.5, condition, ha="left", va="center", fontsize=8)
    ax.set_title("tx (violin colors)", fontsize=9, loc="left")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def all_grains() -> list[GrainKey]:
    grains: list[GrainKey] = []
    for phase in SESSIONS:
        for cond in sorted(CONDITIONS):
            for sex in SEX_ORDER:
                for condition in CONDITION_ORDER:
                    grains.append(
                        GrainKey(session=phase, trial=cond, sex=sex, condition=condition)
                    )
    return grains


def batch_grains(
    trial: str,
    sex: str,
    *,
    phases: tuple[str, ...] | None = None,
    txs: tuple[str, ...] | None = None,
) -> list[GrainKey]:
    """All phase × tx cells for one condition × sex (first-run helper)."""
    phase_list = phases if phases is not None else SESSIONS
    tx_list = txs if txs is not None else CONDITION_ORDER
    return [
        GrainKey(session=ph, trial=trial, sex=sex, condition=condition)
        for ph in phase_list
        for condition in tx_list
    ]


def all_condition_overlay_grains() -> list[TxOverlayGrainKey]:
    grains: list[TxOverlayGrainKey] = []
    for phase in SESSIONS:
        for cond in sorted(CONDITIONS):
            for sex in SEX_ORDER:
                grains.append(
                    TxOverlayGrainKey(session=phase, trial=cond, sex=sex)
                )
    return grains


def batch_condition_overlay_grains(
    trial: str,
    sex: str,
    *,
    phases: tuple[str, ...] | None = None,
) -> list[TxOverlayGrainKey]:
    phase_list = phases if phases is not None else SESSIONS
    return [
        TxOverlayGrainKey(session=ph, trial=trial, sex=sex)
        for ph in phase_list
    ]


def run_grain(
    grain: GrainKey,
    *,
    nor_h5_path: Path,
    ensemble_root: Path,
    prototypes_csv: Path,
    video_root: Path,
    out_dir: Path,
    models: list[str] | None = None,
    frame_stride: int = DEFAULT_FRAME_STRIDE,
    bg_frame_stride: int | None = None,
    blur_sigma: float = DEFAULT_BLUR_SIGMA,
    vmax_s: float | None = None,
    max_sessions: int | None = None,
    keep_clusters: frozenset[int] | None = None,
) -> dict[str, object]:
    from nor_object_mi.fig_simpler_first_syllable_signatures import (  # noqa: E402
        build_cluster_color_lookup,
    )

    if not HAS_CV2:
        raise RuntimeError("opencv-python required for spatial heatmaps")

    models = models or discover_paramscan_models(ensemble_root)
    proto = pd.read_csv(prototypes_csv)
    cluster_lookup = build_cluster_lookup(proto)
    _lookup, all_cluster_ids, _cmap = build_cluster_color_lookup(
        proto[["cluster_id"]].drop_duplicates().assign(n_bouts=1)
    )
    if keep_clusters is not None:
        cluster_ids = [c for c in all_cluster_ids if c in keep_clusters]
        if not cluster_ids:
            cluster_ids = sorted(keep_clusters)
        colors = cluster_colors_bgr(cluster_ids, _lookup)
    else:
        cluster_ids = all_cluster_ids
        colors = cluster_colors_bgr(cluster_ids + [NOISE_CLUSTER], _lookup)

    with h5py.File(nor_h5_path, "r") as nor_h5:
        kpms_index = build_kpms_index(ensemble_root, models)
        sessions = list(iter_grain_sessions(nor_h5, kpms_index, grain))
        if max_sessions is not None:
            sessions = sessions[: int(max_sessions)]

    if not sessions:
        return {"grain": grain.slug(), "status": "empty", "n_sessions": 0}, [], {}

    _ = bg_frame_stride  # retained CLI/API; median video bg disabled
    canonical_hw = resolve_canonical_hw(sessions, video_root)
    keep_note = (
        f" keep_clusters={sorted(keep_clusters)}" if keep_clusters is not None else ""
    )
    print(
        f"grain {grain.slug()}: n_sessions={len(sessions)} models={len(models)} "
        f"canvas={canonical_hw[1]}x{canonical_hw[0]} "
        f"bg=none dwell_stride={frame_stride}{keep_note}",
        flush=True,
    )

    with h5py.File(nor_h5_path, "r") as nor_h5:
        dwell, dwell_stats = accumulate_cluster_dwell(
            nor_h5,
            ensemble_root,
            sessions,
            models,
            cluster_lookup,
            video_root=video_root,
            canonical_hw=canonical_hw,
            frame_stride=frame_stride,
            blur_sigma=blur_sigma,
            keep_clusters=keep_clusters,
        )
        markers = loci_markers_for_grain(
            nor_h5,
            sessions,
            trial=grain.trial,
            canonical_hw=canonical_hw,
            video_root=video_root,
        )
        arena_bbox = mean_arena_bbox_for_grain(
            nor_h5,
            sessions,
            canonical_hw=canonical_hw,
            video_root=video_root,
        )

    canvas = blank_canvas(canonical_hw)
    composite = composite_dwell_overlay(canvas, dwell, colors, vmax_s=vmax_s)
    draw_arena_outline(composite, arena_bbox)
    draw_loci_markers(composite, markers)
    n_rotated = int(sum(1 for s in sessions if s.rotate_180))
    draw_rotation_notation(composite, n_rotated=n_rotated, n_sessions=len(sessions))
    draw_condition_notation(composite, grain.condition)
    if keep_clusters is not None and len(keep_clusters) == 1:
        only = next(iter(keep_clusters))
        _put_outlined_text(composite, f"cluster {only}", (8, 44), scale=0.5)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / f"fig_syllable_spatial_{grain.slug()}"
    cv2.imwrite(str(stem.with_suffix(".png")), composite)

    summary = {
        "grain": grain.slug(),
        "session": grain.session,
        "trial": grain.trial,
        "sex": grain.sex,
        "condition": grain.condition,
        "n_sessions": len(sessions),
        "n_models": len(models),
        "n_rotated_180": n_rotated,
        "loci_markers": [{"x": m.x, "y": m.y, "label": m.label} for m in markers],
        "arena_bbox_xyxy": (
            [float(v) for v in arena_bbox.tolist()] if arena_bbox is not None else None
        ),
        "alignment": "fam_left_via_rot180",
        "background": "blank",
        "frame_stride": frame_stride,
        "blur_sigma": blur_sigma,
        "canonical_hw": [int(canonical_hw[0]), int(canonical_hw[1])],
        **dwell_stats,
        "output_png": str(stem.with_suffix(".png")),
    }
    (out_dir / f"grain_{grain.slug()}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"wrote {stem.with_suffix('.png')}", flush=True)
    return summary, cluster_ids, colors


def run_condition_overlay_grain(
    grain: TxOverlayGrainKey,
    *,
    nor_h5_path: Path,
    ensemble_root: Path,
    prototypes_csv: Path,
    video_root: Path,
    out_dir: Path,
    models: list[str] | None = None,
    frame_stride: int = DEFAULT_FRAME_STRIDE,
    bg_frame_stride: int | None = None,
    blur_sigma: float = DEFAULT_BLUR_SIGMA,
    vmax_s: float | None = None,
    max_sessions: int | None = None,
    keep_clusters: frozenset[int] | None = None,
) -> dict[str, object]:
    if not HAS_CV2:
        raise RuntimeError("opencv-python required for spatial heatmaps")
    if keep_clusters is None:
        raise ValueError("tx overlay mode requires keep_clusters (e.g. cluster 13)")

    models = models or discover_paramscan_models(ensemble_root)
    proto = pd.read_csv(prototypes_csv)
    cluster_lookup = build_cluster_lookup(proto)
    colors = tx_colors_bgr()

    with h5py.File(nor_h5_path, "r") as nor_h5:
        kpms_index = build_kpms_index(ensemble_root, models)
        sessions = list(iter_grain_sessions(nor_h5, kpms_index, grain))
        if max_sessions is not None:
            sessions = sessions[: int(max_sessions)]

    if not sessions:
        return {"grain": grain.slug(), "status": "empty", "n_sessions": 0}, [], {}

    _ = bg_frame_stride
    canonical_hw = resolve_canonical_hw(sessions, video_root)
    keep_note = f" keep_clusters={sorted(keep_clusters)} color_by=tx"
    print(
        f"grain {grain.slug()}: n_sessions={len(sessions)} models={len(models)} "
        f"canvas={canonical_hw[1]}x{canonical_hw[0]} "
        f"bg=none dwell_stride={frame_stride}{keep_note}",
        flush=True,
    )

    with h5py.File(nor_h5_path, "r") as nor_h5:
        dwell, dwell_stats = accumulate_condition_dwell(
            nor_h5,
            ensemble_root,
            sessions,
            models,
            cluster_lookup,
            video_root=video_root,
            canonical_hw=canonical_hw,
            frame_stride=frame_stride,
            blur_sigma=blur_sigma,
            keep_clusters=keep_clusters,
        )
        markers = loci_markers_for_grain(
            nor_h5,
            sessions,
            trial=grain.trial,
            canonical_hw=canonical_hw,
            video_root=video_root,
        )
        arena_bbox = mean_arena_bbox_for_grain(
            nor_h5,
            sessions,
            canonical_hw=canonical_hw,
            video_root=video_root,
        )

    canvas = blank_canvas(canonical_hw)
    composite = composite_dwell_overlay(canvas, dwell, colors, vmax_s=vmax_s)
    draw_arena_outline(composite, arena_bbox)
    draw_loci_markers(composite, markers)
    n_rotated = int(sum(1 for s in sessions if s.rotate_180))
    draw_rotation_notation(composite, n_rotated=n_rotated, n_sessions=len(sessions))
    if len(keep_clusters) == 1:
        only = next(iter(keep_clusters))
        _put_outlined_text(composite, f"cluster {only}", (8, 44), scale=0.5)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / f"fig_syllable_spatial_{grain.slug()}"
    cv2.imwrite(str(stem.with_suffix(".png")), composite)

    summary = {
        "grain": grain.slug(),
        "session": grain.session,
        "trial": grain.trial,
        "sex": grain.sex,
        "condition": "all_tx",
        "n_sessions": len(sessions),
        "n_models": len(models),
        "n_rotated_180": n_rotated,
        "loci_markers": [{"x": m.x, "y": m.y, "label": m.label} for m in markers],
        "arena_bbox_xyxy": (
            [float(v) for v in arena_bbox.tolist()] if arena_bbox is not None else None
        ),
        "alignment": "fam_left_via_rot180",
        "background": "blank",
        "color_by": "condition",
        "frame_stride": frame_stride,
        "blur_sigma": blur_sigma,
        "canonical_hw": [int(canonical_hw[0]), int(canonical_hw[1])],
        **dwell_stats,
        "output_png": str(stem.with_suffix(".png")),
    }
    (out_dir / f"grain_{grain.slug()}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"wrote {stem.with_suffix('.png')}", flush=True)
    return summary, list(CONDITION_ORDER), colors
