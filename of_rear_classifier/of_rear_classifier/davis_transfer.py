"""Goal B: train Sturman-annotator MLPs → apply on Davis SA videos vs human labels.

Trains **one model per Sturman experimenter** (Jin / Furkan / Oliver) on **all**
Sturman OFT videos, then scores each model on Davis videos (e.g. Test 10, 42)
against a local scorer CSV (``model/labels/<scorer>.csv``).

Claim type: **validation** (domain transfer), not LOOCV verification.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from of_rear_classifier.bout import avgbool, bout_count, bout_time_s
from of_rear_classifier.label_store import load_labels
from of_rear_classifier.labels import CLASS_NAMES, DEFAULT_CLASS, load_sturman_oft_labels
from of_rear_classifier.sa_features import load_sa_video_features
from of_rear_classifier.sturman_dlc import (
    DEFAULT_CUT_END,
    DEFAULT_CUT_START,
    DEFAULT_FPS,
    DEFAULT_LIKELIHOOD_CUTOFF,
    load_sturman_video_features,
)
from of_rear_classifier.sturman_loocv import EXPERIMENTERS, _labels_on_cut
from of_rear_classifier.train_torch import (
    CLASS_TO_IDX,
    features_to_window_xy,
    predict_classes,
    predict_proba,
    train_mlp,
)
from of_rear_classifier.window import DEFAULT_INTEGRATION_WINDOW

BEH_TYPES = ("Supported", "Unsupported", "Grooming")


@dataclass
class TransferRow:
    experimenter: str
    video_id: str
    davis_scorer: str
    n_eval: int
    frame_acc: float
    frame_acc_beh_only: float
    supported_time_pred_s: float
    supported_time_exp_s: float
    unsupported_time_pred_s: float
    unsupported_time_exp_s: float
    grooming_time_pred_s: float
    grooming_time_exp_s: float
    supported_count_pred: int
    supported_count_exp: int
    unsupported_count_pred: int
    unsupported_count_exp: int
    train_acc: float
    train_n: int
    seconds: float


def paint_davis_frame_labels(labels: pd.DataFrame, *, n_frames: int) -> tuple[np.ndarray, np.ndarray]:
    """Paint scorer intervals onto frames.

    Returns ``(y, covered)`` where ``covered`` marks any labeled frame (incl. ``None``).
    Uncovered frames are ``None`` (default class) but ``covered=False``.
    """
    y = np.full(n_frames, DEFAULT_CLASS, dtype=object)
    covered = np.zeros(n_frames, dtype=bool)
    if labels is None or labels.empty:
        return y, covered
    for _, row in labels.iterrows():
        lab = str(row.get("label", "") or "").strip()
        if not lab or lab in {"nan", "NaN", "<NA>"}:
            continue
        t0 = int(row["t0_frame"])
        t1 = int(row["t1_frame"])
        t0 = max(0, t0)
        t1 = min(n_frames - 1, t1)
        if t1 < t0:
            continue
        y[t0 : t1 + 1] = lab
        covered[t0 : t1 + 1] = True
    return y, covered


def discover_sa_h5(h5_dir: Path, video_id: str) -> Path:
    hits = sorted(Path(h5_dir).glob(f"{video_id}_superanimal*.h5"))
    if not hits:
        raise FileNotFoundError(f"no SA H5 for {video_id} under {h5_dir}")
    return hits[0]


def default_labels_csv(kpms_root: Path, video_id: str, scorer: str) -> Path:
    return Path(kpms_root) / video_id / "model" / "labels" / f"{scorer}.csv"


def run_davis_transfer(
    *,
    oft_root: Path,
    davis_videos: list[str],
    sa_h5_dir: Path,
    kpms_root: Path,
    quad_csv: Path,
    davis_scorer: str,
    out_dir: Path,
    experimenters: tuple[str, ...] = EXPERIMENTERS,
    fps_sturman: float = DEFAULT_FPS,
    fps_davis: float | None = None,
    integration_window: int = DEFAULT_INTEGRATION_WINDOW,
    epochs: int = 10,
    batch_size: int = 256,
    device: str | None = None,
    seed: int = 0,
    avgbool_window: int = 10,
) -> pd.DataFrame:
    oft_root = Path(oft_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    labels_path = oft_root / "Labels" / "AllLabDataOFT_final.csv"
    csv_dir = oft_root / "Output_DLC"
    sturman_labels = load_sturman_oft_labels(labels_path)
    id_dlc = sturman_labels.groupby("ID")["DLCFile"].first().astype(str).to_dict()
    video_ids = sorted(id_dlc.keys())

    # --- Sturman feature cache ---
    feat_cache: dict[str, np.ndarray] = {}
    print(f"loading {len(video_ids)} Sturman DLC CSVs…", flush=True)
    t0 = time.perf_counter()
    for i, vid in enumerate(video_ids, start=1):
        path = csv_dir / id_dlc[vid]
        feat_z, _meta = load_sturman_video_features(
            path,
            likelihood_cutoff=DEFAULT_LIKELIHOOD_CUTOFF,
            cut_start=DEFAULT_CUT_START,
            cut_end=DEFAULT_CUT_END,
        )
        feat_cache[vid] = feat_z
        print(f"  [{i}/{len(video_ids)}] {vid} T={feat_z.shape[0]}", flush=True)
    print(f"sturman features {time.perf_counter() - t0:.1f}s", flush=True)

    # --- Train one model per experimenter on ALL Sturman videos ---
    models: dict[str, object] = {}
    train_meta: dict[str, dict] = {}
    for ei, exp in enumerate(experimenters):
        print(f"\ntraining Sturman→{exp} on all {len(video_ids)} videos…", flush=True)
        xs, ys = [], []
        for vid in video_ids:
            lab = sturman_labels[(sturman_labels["Experimenter"] == exp) & (sturman_labels["ID"] == vid)]
            y_frames = _labels_on_cut(
                lab,
                n_frames=feat_cache[vid].shape[0],
                fps=fps_sturman,
                cut_start=DEFAULT_CUT_START,
                keep_types=BEH_TYPES,
            )
            xw, yw = features_to_window_xy(
                feat_cache[vid], y_frames, integration_window=integration_window
            )
            xs.append(xw)
            ys.append(yw)
        x_train = np.concatenate(xs, axis=0)
        y_train = np.concatenate(ys, axis=0)
        result = train_mlp(
            x_train,
            y_train,
            epochs=epochs,
            batch_size=batch_size,
            seed=seed + ei,
            device=device,
        )
        models[exp] = result.model
        train_meta[exp] = {"train_acc": result.train_acc, "train_n": result.n_train}
        print(
            f"  {exp}: train_acc={result.train_acc:.3f} n={result.n_train}",
            flush=True,
        )

    # --- Davis videos ---
    w = int(integration_window)
    rows: list[TransferRow] = []
    for video_id in davis_videos:
        h5 = discover_sa_h5(sa_h5_dir, video_id)
        print(f"\nDavis {video_id}: loading {h5.name}…", flush=True)
        feat_z, meta = load_sa_video_features(h5, quad_csv=quad_csv, video_stem=video_id)
        n_frames = int(meta["n_frames"])
        fps = float(fps_davis) if fps_davis else _guess_fps(video_id)

        lab_path = default_labels_csv(kpms_root, video_id, davis_scorer)
        davis_lab = load_labels(lab_path, scorer=davis_scorer)
        y_true_full, covered = paint_davis_frame_labels(davis_lab, n_frames=n_frames)
        print(
            f"  T={n_frames} fps≈{fps:.2f} labeled_frames={int(covered.sum())} "
            f"from {lab_path.name}",
            flush=True,
        )

        # Window features once; labels aligned to centers [W, T-W)
        x_all, y_win = features_to_window_xy(
            feat_z, y_true_full, integration_window=integration_window
        )
        covered_win = covered[w : n_frames - w]
        assert y_win is not None and len(y_win) == len(covered_win)

        for exp, model in models.items():
            fold_t0 = time.perf_counter()
            pred_all = predict_classes(model, x_all, device=device)
            proba_all = predict_proba(model, x_all, device=device)
            # Eval only on human-covered centers
            mask = covered_win
            if not np.any(mask):
                print(f"  [{exp}] no covered frames — skip", flush=True)
                continue
            pred = pred_all[mask]
            y_te = y_win[mask]
            frame_acc = float(np.mean(pred == y_te))
            beh = y_te != DEFAULT_CLASS
            frame_acc_beh = float(np.mean(pred[beh] == y_te[beh])) if np.any(beh) else float("nan")

            # Bout metrics on full windowed stream (human paint; uncovered=None)
            bout = _bout_metrics(pred_all, y_win, fps=fps, avgbool_window=avgbool_window)
            row = TransferRow(
                experimenter=exp,
                video_id=video_id,
                davis_scorer=davis_scorer,
                n_eval=int(mask.sum()),
                frame_acc=frame_acc,
                frame_acc_beh_only=frame_acc_beh,
                train_acc=float(train_meta[exp]["train_acc"]),
                train_n=int(train_meta[exp]["train_n"]),
                seconds=time.perf_counter() - fold_t0,
                **bout,
            )
            rows.append(row)
            print(
                f"  [{exp}] n_eval={row.n_eval} acc={frame_acc:.3f} "
                f"acc_beh={frame_acc_beh:.3f} "
                f"sup_t {row.supported_time_pred_s:.1f}/{row.supported_time_exp_s:.1f}s "
                f"unsup_t {row.unsupported_time_pred_s:.1f}/{row.unsupported_time_exp_s:.1f}s",
                flush=True,
            )

            # Framewise pred + softmax for labeler import (quote "None" for pandas).
            pred_path = out_dir / f"pred_{video_id}_{exp}.csv"
            centers = np.arange(w, n_frames - w)
            out = {
                "frame": centers,
                "y_true": np.asarray(y_win, dtype=str),
                "y_pred": np.asarray(pred_all, dtype=str),
                "covered": covered_win.astype(int),
            }
            for name, idx in CLASS_TO_IDX.items():
                out[f"p_{name}"] = proba_all[:, idx]
            pd.DataFrame(out).to_csv(pred_path, index=False, quoting=1)

    df = pd.DataFrame([asdict(r) for r in rows])
    metrics_path = out_dir / "transfer_metrics.csv"
    df.to_csv(metrics_path, index=False)
    summary = _summarize(df)
    summary["davis_videos"] = list(davis_videos)
    summary["davis_scorer"] = davis_scorer
    summary["class_names"] = list(CLASS_NAMES)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"wrote {metrics_path}", flush=True)
    print(f"wrote {summary_path}", flush=True)
    return df


def _guess_fps(video_id: str) -> float:
    import cv2

    for root in (
        Path(r"D:\Open Field Frailty\Open Field - mp4"),
        Path(r"D:\Open Field - mp4"),
    ):
        mp4 = root / f"{video_id}.mp4"
        if mp4.is_file():
            cap = cv2.VideoCapture(str(mp4))
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            cap.release()
            return fps
    return 30.0


def _bout_metrics(pred: np.ndarray, y_true: np.ndarray, *, fps: float, avgbool_window: int) -> dict:
    out: dict = {}
    for name, key in (
        ("Supported", "supported"),
        ("Unsupported", "unsupported"),
        ("Grooming", "grooming"),
    ):
        p_s = avgbool(pred == name, avgbool_window)
        e_s = avgbool(y_true == name, avgbool_window)
        out[f"{key}_time_pred_s"] = bout_time_s(p_s, fps)
        out[f"{key}_time_exp_s"] = bout_time_s(e_s, fps)
        if name != "Grooming":
            out[f"{key}_count_pred"] = bout_count(p_s)
            out[f"{key}_count_exp"] = bout_count(e_s)
    return out


def _summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n_rows": 0}
    summary: dict = {
        "n_rows": int(len(df)),
        "mean_frame_acc": float(df["frame_acc"].mean()),
        "mean_frame_acc_beh_only": float(df["frame_acc_beh_only"].mean()),
        "by_experimenter": {},
        "by_video": {},
    }
    for exp, g in df.groupby("experimenter"):
        summary["by_experimenter"][str(exp)] = {
            "mean_frame_acc": float(g["frame_acc"].mean()),
            "mean_frame_acc_beh_only": float(g["frame_acc_beh_only"].mean()),
            "n": int(len(g)),
        }
    for vid, g in df.groupby("video_id"):
        summary["by_video"][str(vid)] = {
            "mean_frame_acc": float(g["frame_acc"].mean()),
            "mean_frame_acc_beh_only": float(g["frame_acc_beh_only"].mean()),
            "n": int(len(g)),
        }
    return summary
